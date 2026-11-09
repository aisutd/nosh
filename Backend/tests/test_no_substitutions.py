"""No-substitution requests keep full validation without demanding replacements."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from llm import nosh_generation as llm
from personalization import MEMORY_RULES

SOURCE = 'Recipe: Berry syrup\nIngredients: 1 cup water, 1 cup white sugar, 2 cups strawberries\nDirections: Combine and boil for 10 minutes.'
ANSWER = 'Recipe Name: Berry syrup\nChanges:\n- none\nSteps:\n1. Combine 1 cup water, 1 cup white sugar and 2 cups strawberries and boil for 10 minutes.'
PASS = json.dumps({'result': 'PASS', 'explanation': 'Matches source.', 'violations': []})


class NoSubstitutionTests(unittest.TestCase):
    @patch.object(llm.ollama, 'chat')
    def test_generation_and_judgment_explicitly_allow_unchanged_recipe(self, chat):
        chat.return_value = SimpleNamespace(message=SimpleNamespace(content=ANSWER))
        llm.generate_recipe('strawberries', SOURCE, substitutions=[])
        self.assertIn(llm.NO_SUBSTITUTION_RULES, chat.call_args.kwargs['messages'][0]['content'])
        self.assertIn(MEMORY_RULES, chat.call_args.kwargs['messages'][0]['content'])
        chat.return_value = SimpleNamespace(message=SimpleNamespace(content=PASS))
        self.assertTrue(llm.judge_passed(llm.evaluate_generation('strawberries', SOURCE, ANSWER, substitutions=[])))
        self.assertIn(llm.NO_SUBSTITUTION_RULES, chat.call_args.kwargs['messages'][0]['content'])
        self.assertIn(llm.JUDGE_SYSTEM_RULES, chat.call_args.kwargs['messages'][0]['content'])

    @patch.object(llm.ollama, 'chat')
    def test_changed_quantity_still_rejected_before_judge(self, chat):
        verdict = llm.evaluate_generation('strawberries', SOURCE, ANSWER.replace('2 cups strawberries', '1 cup strawberries'))
        self.assertFalse(llm.judge_passed(verdict))
        chat.assert_not_called()

    @patch.object(llm.ollama, 'chat')
    def test_substitution_generation_keeps_existing_rules(self, chat):
        chat.return_value = SimpleNamespace(message=SimpleNamespace(content=ANSWER))
        plan = [{'ingredient': 'honey', 'replacement_ingredients': ['sugar', 'water']}]
        llm.generate_recipe('strawberries, sugar, water', SOURCE, substitutions=plan)
        self.assertNotIn(llm.NO_SUBSTITUTION_RULES, chat.call_args.kwargs['messages'][0]['content'])
