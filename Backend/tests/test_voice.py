"""Voice routing tests use isolated fakes, never production service bypasses."""
import sys
import unittest
from types import ModuleType
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.voice import VoiceTurn, handle_turn, recipe_steps, router
from security import get_optional_user

RECIPE = 'Recipe Name: Toast\nChanges:\n- None\nSteps:\n1. Toast bread.\n2. Serve warm.'


class VoiceTests(unittest.TestCase):
    def test_only_numbered_directions_are_navigated(self):
        self.assertEqual(recipe_steps('Ingredients:\n1. Bread'), [])
        self.assertEqual(recipe_steps(RECIPE), ['Toast bread.', 'Serve warm.'])

    def test_navigation_bounds_and_independent_state(self):
        first = handle_turn(VoiceTurn(message='next step', recipe=RECIPE))
        self.assertEqual(first['step'], 0)
        self.assertEqual(handle_turn(VoiceTurn(message='next step', recipe=RECIPE, step=0))['step'], 1)
        self.assertEqual(handle_turn(VoiceTurn(message='next step', recipe=RECIPE, step=1))['step'], 1)
        self.assertEqual(handle_turn(VoiceTurn(message='repeat', recipe=RECIPE, step=0)), first)
        self.assertEqual(handle_turn(VoiceTurn(message='next step', recipe=RECIPE))['step'], 0)
        self.assertEqual(handle_turn(VoiceTurn(message='how do I do step 1?'))['step'], -1)

    def test_generation_uses_existing_pipeline(self):
        pipeline = ModuleType('nosh_pipeline')
        calls = []
        def generate(ingredients, **kwargs):
            calls.append(ingredients)
            return {'status': 'ok', 'recipe': RECIPE}
        pipeline.run_nosh = generate
        with patch.dict(sys.modules, {'nosh_pipeline': pipeline}):
            result = handle_turn(VoiceTurn(message='What can I cook?', ingredients=['bread']))
        self.assertEqual(calls, [['bread']])
        self.assertEqual(result['recipe'], RECIPE)
        self.assertEqual(result['step'], -1)

    def test_questions_use_context_and_fail_closed(self):
        chat = ModuleType('llm.recipe_chat')
        generation = ModuleType('llm.nosh_generation')
        contexts = []
        def answer(context, question, history):
            contexts.append(context)
            return {'status': 'answered', 'answer': 'Draft answer'}
        chat.answer_question = answer
        chat.judge_answer = lambda *args: 'FAIL'
        generation.judge_passed = lambda verdict: verdict == 'PASS'
        with patch.dict(sys.modules, {'llm.recipe_chat': chat, 'llm.nosh_generation': generation}):
            result = handle_turn(VoiceTurn(message='How long?', recipe=RECIPE))
        self.assertEqual(contexts[0]['approved_recipe'], RECIPE)
        self.assertNotEqual(result['answer'], 'Draft answer')

    def test_endpoint_validation_and_service_failure(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_optional_user] = lambda: None
        with TestClient(app) as client:
            self.assertEqual(client.post('/voice/turn', json={'message': ' '}).status_code, 400)
            self.assertEqual(client.post('/voice/turn', json={'message': 'x' * 2001}).status_code, 422)
            self.assertEqual(client.post('/voice/turn', json={'message': 'next'}).status_code, 200)
            with patch('routes.voice.handle_turn', side_effect=RuntimeError('private detail')):
                response = client.post('/voice/turn', json={'message': 'hello'})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private detail', response.text)


if __name__ == '__main__':
    unittest.main()
