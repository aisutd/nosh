"""Merge regressions: both desktop RAG interfaces remain usable without audio."""
import ast
import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('merged_voice_client', ROOT / 'voice-agent' / 'rag_client.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class VoiceClientMergeTests(unittest.TestCase):
    def test_http_default_preserves_result_and_request(self):
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'result': {'status': 'ok', 'recipe': 'Soup', 'source_recipe': 'Source', 'source_url': 'https://example.com'}})
        with patch.dict(os.environ, {'NOSH_RAG_MODE': 'http'}), patch.object(client.requests, 'post', return_value=response) as post:
            result = client.generate_recipe(['lentil'], 'Make soup')
        self.assertTrue(result['success'])
        self.assertEqual(result['recipe'], 'Soup')
        self.assertEqual(post.call_args.kwargs['json'], {'ingredients': ['lentil'], 'user_query': 'Make soup'})

    def test_direct_mode_and_mock_main_interface(self):
        pipeline = ModuleType('nosh_pipeline')
        calls = []
        def run(ingredients, **kwargs):
            calls.append((ingredients, kwargs))
            return {'status': 'ok', 'recipe': 'Soup'}
        pipeline.run_nosh = run
        with patch.dict(sys.modules, {'nosh_pipeline': pipeline}), patch.dict(os.environ, {'NOSH_RAG_MODE': 'direct'}), patch.object(client.requests, 'post', side_effect=AssertionError('Direct mode must not use HTTP')):
            self.assertEqual(client.generate_recipe(['lentil'], 'Make soup')['recipe'], 'Soup')
            self.assertEqual(client.ask_rag('Make soup', 'lentil', 'Existing context'), 'Soup')
        self.assertEqual(calls[0], (['lentil'], {'user_query': 'Make soup'}))
        self.assertEqual(calls[1], ('lentil', {'user_query': 'Make soup'}))

    def test_direct_refusal_is_not_a_recipe(self):
        pipeline = ModuleType('nosh_pipeline')
        pipeline.run_nosh = lambda *args, **kwargs: {'status': 'no_recipes_found', 'message': 'No matching source'}
        with patch.dict(sys.modules, {'nosh_pipeline': pipeline}), patch.dict(os.environ, {'NOSH_RAG_MODE': 'direct'}):
            self.assertEqual(client.generate_recipe(['lentil']), {'success': False, 'message': 'No matching source'})
            self.assertEqual(client.ask_rag('Soup', 'lentil'), 'No matching source')

    def test_http_unavailable_is_handled(self):
        with patch.dict(os.environ, {'NOSH_RAG_MODE': 'http'}), patch.object(client.requests, 'post', side_effect=client.requests.exceptions.ConnectionError):
            self.assertFalse(client.generate_recipe(['lentil'])['success'])

    def test_desktop_agent_syntax_and_ingredient_commands_preserved(self):
        tree = ast.parse((ROOT / 'voice-agent' / 'voice_agent.py').read_text())
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertTrue({'add_ingredient', 'remove_ingredient', 'list_ingredients', 'clear_ingredients', 'handle_recipe_context'}.issubset(names))


if __name__ == '__main__':
    unittest.main()
