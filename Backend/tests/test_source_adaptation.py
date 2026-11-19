import csv
import unittest
from pathlib import Path
from unittest.mock import patch
from retrieval.ingredients import normalize_available
from retrieval.substitutions import plan_substitutions
from llm.source_adaptation import build_source_adaptation, build_inventory_ingredients
from llm.nosh_generation import source_quantity_problems, output_format_problems
import nosh_pipeline as pipeline


class SourceAdaptationTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "data/processed/cleaned_recipes.csv"
        with path.open() as f:
            row = next(r for r in csv.DictReader(f) if r['recipe_name'] == 'Apricot Muffins')
        self.recipe = {'title': row['recipe_name'], 'metadata': row,
                       'url': row.get('url', ''), 'similarity': 1,
                       'document': f"Ingredients: {row['ingredients']}\nDirections: {row['directions']}"}
        self.pantry = 'dried apricots, flour, sugar, baking soda, butter, vegetable oil, egg, milk, lemon'
        self.plan = plan_substitutions(row['ingredients'], normalize_available(self.pantry, semantic=False))

    def test_apricot_quantities_and_method_are_preserved(self):
        answer = build_source_adaptation(self.recipe, self.plan)
        self.assertIsNotNone(answer)
        self.assertEqual(output_format_problems(answer), [])
        self.assertEqual(source_quantity_problems(self.recipe['document'], answer, self.plan), [])
        steps = answer.split('Steps:', 1)[1]
        for text in ('¾ cup white sugar', '½ teaspoon salt', '¼ cup melted butter', '¼ cup vegetable oil', '1  egg', '400 degrees F', '15 minutes', 'rest 5 minutes'):
            self.assertIn(text, steps)
        self.assertNotIn('buttermilk', steps)
        original = self.recipe['metadata']['directions']
        for paragraph in original.splitlines():
            if paragraph.strip():
                self.assertIn(paragraph.replace('buttermilk', 'prepared milk and lemon mixture'), answer)

    def test_scaled_buttermilk_uses_catalog_ratio(self):
        self.recipe['metadata']['ingredients'] = self.recipe['metadata']['ingredients'].replace('1 cup buttermilk', '2 cups buttermilk')
        self.assertIn("30 tablespoon milk", build_source_adaptation(self.recipe, self.plan))

    def test_missing_directions_falls_back(self):
        self.recipe['metadata']['directions'] = ''
        self.assertIsNone(build_source_adaptation(self.recipe, self.plan))

    def test_pipeline_validates_preserved_draft_without_generation(self):
        with patch.object(pipeline, 'classify_request', return_value={'status':'in_scope'}), patch.object(pipeline, 'search_recipes', return_value=[self.recipe]), patch.object(pipeline, 'generate_recipe') as generate, patch.object(pipeline, 'evaluate_generation', return_value='{"result":"PASS","explanation":"ok","violations":[]}') as judge:
            result = pipeline.run_nosh(self.pantry)
        self.assertEqual(result['status'], 'ok')
        generate.assert_not_called()
        judge.assert_called_once()
        self.assertTrue(judge.call_args.kwargs["source_preserving"])

    def test_inventory_uses_replacement_quantities(self):
        lines = build_inventory_ingredients(self.recipe, self.plan)
        self.assertIn("15 tablespoon milk", lines)
        self.assertIn("1 tablespoon lemon juice", lines)
        self.assertFalse(any("buttermilk" in line for line in lines))
        self.assertIn("¾ cup white sugar", lines)

    def test_ambiguous_consumption_requires_manual_inventory_update(self):
        self.recipe['metadata']['ingredients'] = self.recipe['metadata']['ingredients'].replace('1 cup buttermilk', '200 grams buttermilk')
        self.assertIsNone(build_inventory_ingredients(self.recipe, self.plan))

    def test_exact_recipe_keeps_inventory_lines(self):
        self.assertIn("1 cup buttermilk", build_inventory_ingredients(self.recipe, []))


class ReliabilityTests(unittest.TestCase):
    def tea(self):
        with (Path(__file__).resolve().parents[1] / 'data/processed/cleaned_recipes.csv').open() as f:
            row = next(r for r in csv.DictReader(f) if r['recipe_name'] == 'Honey Lemon Tea')
        recipe = {'title': row['recipe_name'], 'metadata': row, 'url': '', 'similarity': 1,
                  'document': f"Ingredients: {row['ingredients']}\nDirections: {row['directions']}"}
        plan = plan_substitutions(row['ingredients'], normalize_available('lemon', semantic=False))
        return recipe, plan

    def test_honey_teaspoons_preserve_separate_source_sugar_and_water(self):
        recipe, plan = self.tea()
        answer = build_source_adaptation(recipe, plan)
        self.assertIn('2 1/2 teaspoon sugar', answer)
        self.assertIn('1/2 teaspoon water', answer)
        self.assertIn('1 teaspoon white sugar', answer)
        self.assertIn('1 cup water', answer)
        self.assertIn('1 minute 30 seconds', answer)
        self.assertNotIn('honey', answer.split('Steps:')[1])
        self.assertEqual(output_format_problems(answer), [])
        self.assertEqual(source_quantity_problems(recipe['document'], answer, plan), [])
        lines = build_inventory_ingredients(recipe, plan)
        self.assertIn('2 1/2 teaspoon sugar', lines)
        self.assertIn('1 teaspoon white sugar', lines)
        self.assertIn('1/2 teaspoon water', lines)

    def test_partial_measured_usage_falls_back(self):
        recipe, plan = self.tea()
        recipe['metadata']['directions'] = 'Add 1 teaspoon honey now and the remainder later.'
        self.assertIsNone(build_source_adaptation(recipe, plan))
        self.assertIsNone(build_inventory_ingredients(recipe, plan))

    def test_ambiguous_duplicate_honey_falls_back(self):
        recipe, plan = self.tea()
        recipe['metadata']['ingredients'] += ', 1 teaspoon honey'
        self.assertIsNone(build_source_adaptation(recipe, plan))

    def test_shared_staples_reach_generator_and_judge(self):
        import json
        from types import SimpleNamespace
        from staples import STAPLES
        from llm import nosh_generation as llm
        recipe, plan = self.tea()
        answer = build_source_adaptation(recipe, plan)
        with patch.object(llm.ollama, 'chat', return_value=SimpleNamespace(message=SimpleNamespace(content=answer))) as chat:
            llm.generate_recipe('lemon', recipe['document'], substitutions=plan)
            generation = json.loads(chat.call_args.kwargs['messages'][1]['content'])
            llm.evaluate_generation('lemon', recipe['document'], answer, substitutions=plan)
            judgment = json.loads(chat.call_args.kwargs['messages'][1]['content'])
        self.assertEqual(generation['assumed_staples'], STAPLES)
        self.assertEqual(judgment['assumed_staples'], STAPLES)
        self.assertIn('sugar', judgment['available_ingredients'])
        self.assertEqual(judgment['substitutions'][0]['scale_factor'], '1/24')
        self.assertEqual(judgment['substitutions'][0]['recipe_components'][0]['quantity'], '2 1/2')
        self.assertEqual(generation['substitutions'], judgment['substitutions'])

    def test_honey_first_candidate_needs_no_rewrite_when_judge_passes(self):
        recipe, plan = self.tea()
        with patch.object(pipeline, 'classify_request', return_value={'status': 'in_scope'}), patch.object(pipeline, 'search_recipes', return_value=[recipe]), patch.object(pipeline, 'generate_recipe') as generate, patch.object(pipeline, 'evaluate_generation', return_value='{"result":"PASS","explanation":"ok","violations":[]}') as judge:
            result = pipeline.run_nosh('lemon')
        self.assertEqual(result['status'], 'ok')
        generate.assert_not_called()
        judge.assert_called_once()
        self.assertTrue(judge.call_args.kwargs["source_preserving"])

    def test_preserved_draft_still_rejects_changed_source_amount(self):
        from llm import nosh_generation as llm
        recipe, plan = self.tea()
        answer = build_source_adaptation(recipe, plan).replace('1 cup water', '2 cups water')
        with patch.object(llm.ollama, 'chat') as chat:
            verdict = llm.evaluate_generation('lemon', recipe['document'], answer,
                                              substitutions=plan, source_preserving=True)
        self.assertFalse(llm.judge_passed(verdict))
        chat.assert_not_called()

    def test_culinary_failure_is_not_bypassed_and_rewrite_gets_full_review(self):
        recipe, plan = self.tea()
        failed = '{"result":"FAIL","explanation":"Unsuitable method","violations":["Unsuitable method"]}'
        with patch.object(pipeline, 'classify_request', return_value={'status': 'in_scope'}), patch.object(pipeline, 'search_recipes', return_value=[recipe]), patch.object(pipeline, 'generate_recipe', return_value='rewritten draft'), patch.object(pipeline, 'evaluate_generation', return_value=failed) as judge:
            result = pipeline.run_nosh('lemon')
        self.assertEqual(result['status'], 'failed_validation')
        self.assertIsNone(result['recipe'])
        self.assertTrue(judge.call_args_list[0].kwargs['source_preserving'])
        self.assertFalse(judge.call_args_list[1].kwargs.get('source_preserving', False))
