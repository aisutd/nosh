"""The real API must serve voice, memory and current inventory/recipe features."""
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from security import get_optional_user


class UnifiedAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def test_one_app_exposes_every_feature(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()['capabilities']), {'recipes', 'inventory', 'voice', 'memory'})
        paths = set(self.client.get('/openapi.json').json()['paths'])
        self.assertTrue({'/voice/turn', '/memory', '/inventory', '/inventory/consume', '/recipes/generate-selected', '/scan'}.issubset(paths))

    def test_voice_uses_current_authenticated_pantry(self):
        app.dependency_overrides[get_optional_user] = lambda: {'ingredients': ['rice'], 'cooking_preferences': {'skill_level': 'confident'}}
        with patch('routes.voice.handle_turn', return_value={'answer': 'Ready', 'step': -1}) as handler:
            response = self.client.post('/voice/turn', json={'message': 'what can i cook', 'ingredients': ['stale pantry']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(handler.call_args.args[0].ingredients, ['rice'])
        self.assertEqual(handler.call_args.args[1]['preferences']['skill_level'], 'confident')

    def test_selected_recipe_retains_servings_and_memory(self):
        app.dependency_overrides[get_optional_user] = lambda: {'cooking_preferences': {'skill_level': 'intermediate'}}
        with patch('routes.pipeline.run_nosh', return_value={'status': 'ok', 'recipe': 'Rice'}) as runner:
            response = self.client.post('/recipes/generate-selected', json={'recipe_id': 'rag:abc', 'ingredients': ['rice'], 'servings': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(runner.call_args.kwargs['servings'], 2)
        self.assertEqual(runner.call_args.kwargs['selected_recipe_id'], 'abc')
        self.assertEqual(runner.call_args.kwargs['personalization']['preferences']['skill_level'], 'intermediate')

    def test_memory_and_inventory_require_auth(self):
        self.assertEqual(self.client.get('/inventory').status_code, 401)
        self.assertEqual(self.client.get('/memory').status_code, 401)


if __name__ == '__main__':
    unittest.main()
