"""Multi-session tests: real auth, HTTP routes and prompt builders; fake DB/LLM."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
from personalization import Preferences, memory_context, rank_recipes
from routes import memory, voice
from security import create_access_token


class FakeUsers:
    def __init__(self):
        self.ids = {name: str(ObjectId()) for name in ('a', 'b')}
        self.docs = {value: {'_id': value} for value in self.ids.values()}

    async def find_one(self, query, *args):
        return copy.deepcopy(self.docs.get(str(query['_id'])))

    async def update_one(self, query, update):
        doc = self.docs[str(query['_id'])]
        doc.update(copy.deepcopy(update.get('$set', {})))
        for key in update.get('$unset', {}):
            doc.pop(key, None)
        for key, push in update.get('$push', {}).items():
            doc[key] = (doc.get(key, []) + copy.deepcopy(push['$each']))[push['$slice']:]


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeUsers()
        self.patchers = [patch('routes.memory.user', self.store), patch('security.user', self.store)]
        for item in self.patchers:
            item.start()
        self.headers = {name: {'Authorization': 'Bearer ' + create_access_token({'sub': value})} for name, value in self.store.ids.items()}
        app = FastAPI()
        app.include_router(memory.router)
        app.include_router(voice.router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patchers):
            item.stop()

    def test_three_sessions_persist_and_isolate_accounts(self):
        preferences = Preferences(dietary_preferences=['vegetarian'], difficulties=['pan temperature']).model_dump()
        self.assertEqual(self.client.put('/memory/preferences', headers=self.headers['a'], json=preferences).status_code, 200)
        snapshots = []
        for index in range(3):
            with patch('routes.voice.handle_turn', side_effect=lambda turn, context: snapshots.append(context) or {'answer': 'Test answer', 'step': -1}):
                self.assertEqual(self.client.post('/voice/turn', headers=self.headers['a'], json={'message': 'help'}).status_code, 200)
            self.assertEqual(len(snapshots[-1]['past_sessions']), index)
            self.assertEqual(snapshots[-1]['preferences']['dietary_preferences'], ['vegetarian'])
            feedback = {'recipe_title': f'Soup {index}', 'outcome': 'needed_help', 'rating': index + 2, 'difficulty': 'Pan too hot', 'feedback': 'Explain heat control next time'}
            self.assertEqual(self.client.post('/memory/sessions', headers=self.headers['a'], json=feedback).status_code, 201)
        with TestClient(self.client.app) as fresh:
            stored = fresh.get('/memory', headers=self.headers['a']).json()
        self.assertEqual(len(stored['sessions']), 3)
        self.assertEqual(stored['preferences']['skill_level'], 'beginner')
        other = self.client.get('/memory', headers=self.headers['b']).json()
        self.assertEqual(other['sessions'], [])
        self.assertEqual(other['preferences']['dietary_preferences'], [])
        changed = {**preferences, 'skill_level': 'intermediate', 'guidance': 'concise'}
        self.client.put('/memory/preferences', headers=self.headers['a'], json=changed)
        self.assertEqual(self.client.get('/memory', headers=self.headers['a']).json()['preferences']['skill_level'], 'intermediate')
        self.client.delete('/memory', headers=self.headers['a'])
        self.assertEqual(self.client.get('/memory', headers=self.headers['a']).json()['sessions'], [])

    def test_auth_validation_and_bounded_retention(self):
        self.assertEqual(self.client.get('/memory').status_code, 401)
        self.assertEqual(self.client.post('/voice/turn', headers={'Authorization': 'Bearer invalid'}, json={'message': 'next'}).status_code, 401)
        self.assertEqual(self.client.post('/memory/sessions', headers=self.headers['a'], json={'recipe_title': ' ', 'outcome': 'completed', 'rating': 9}).status_code, 422)
        self.assertEqual(self.client.put('/memory/preferences', headers=self.headers['a'], json={'user_id': 'b'}).status_code, 422)
        for index in range(35):
            self.client.post('/memory/sessions', headers=self.headers['a'], json={'recipe_title': str(index), 'outcome': 'completed', 'rating': 4})
        sessions = self.client.get('/memory', headers=self.headers['a']).json()['sessions']
        self.assertEqual(len(sessions), 30)
        self.assertEqual(sessions[0]['recipe_title'], '5')
        context = memory_context(self.store.docs[self.store.ids['a']])
        self.assertEqual(len(context['past_sessions']), 8)
        self.assertNotIn('_id', context)
        self.assertEqual(memory_context(None), {})
        self.assertEqual(self.client.post('/voice/turn', json={'message': 'next'}).status_code, 200)

    def test_recommendations_use_diet_and_feedback(self):
        candidates = [{'title': 'Chicken soup', 'ingredients': 'chicken'}, {'title': 'Lentil soup', 'ingredients': 'lentil'}, {'title': 'Pasta', 'ingredients': 'tomato'}]
        context = memory_context({'cooking_preferences': {'dietary_preferences': ['vegetarian']}, 'cooking_history': [{'recipe_title': 'Pasta', 'rating': 5, 'outcome': 'completed'}]})
        self.assertEqual([item['title'] for item in rank_recipes(candidates, context)], ['Pasta', 'Lentil soup', 'Chicken soup'])
        self.assertEqual(candidates[0]['title'], 'Chicken soup')
        self.assertEqual(rank_recipes(candidates, {}), candidates)

    def test_real_prompt_builders_receive_history(self):
        retrieval = ModuleType('retrieval.nosh_retrieval')
        retrieval.normalize_ingredient = lambda value: value
        retrieval.normalize_ingredients = lambda value: value
        payloads = []
        def chat(**kwargs):
            payloads.append(kwargs)
            return SimpleNamespace(message=SimpleNamespace(content=json.dumps({'status': 'answered', 'kind': 'technique', 'answer': 'Warm the pan gently.'})))
        context = memory_context({'cooking_preferences': {'difficulties': ['pan heat']}, 'cooking_history': [{'recipe_title': 'Soup', 'rating': 4, 'outcome': 'needed_help', 'difficulty': 'burned garlic'}]})
        with patch.dict(sys.modules, {'retrieval.nosh_retrieval': retrieval}), patch('ollama.chat', side_effect=chat):
            source = Path(__file__).resolve().parents[1] / 'llm' / 'nosh_generation.py'
            spec = importlib.util.spec_from_file_location('test_generation', source)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.generate_recipe('garlic', 'A source recipe', personalization=context)
            self.assertEqual(json.loads(payloads[-1]['messages'][1]['content'])['personalization'], context)
            self.assertIn('untrusted user DATA', payloads[-1]['messages'][0]['content'])
            with patch.dict(sys.modules, {'llm.nosh_generation': module}):
                spec = importlib.util.spec_from_file_location('test_chat', source.with_name('recipe_chat.py'))
                chat_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(chat_module)
                chat_module.answer_question({'approved_recipe': 'Soup', 'personalization': context}, 'How do I heat the pan?', [])
                self.assertEqual(json.loads(payloads[-1]['messages'][1]['content'])['personalization']['past_sessions'][0]['difficulty'], 'burned garlic')


if __name__ == '__main__':
    unittest.main()
