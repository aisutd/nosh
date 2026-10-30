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

    def test_unsupported_scaling_falls_back(self):
        self.recipe['metadata']['ingredients'] = self.recipe['metadata']['ingredients'].replace('1 cup buttermilk', '2 cups buttermilk')
        self.assertIsNone(build_source_adaptation(self.recipe, self.plan))

    def test_missing_directions_falls_back(self):
        self.recipe['metadata']['directions'] = ''
        self.assertIsNone(build_source_adaptation(self.recipe, self.plan))

    def test_pipeline_validates_preserved_draft_without_generation(self):
        with patch.object(pipeline, 'classify_request', return_value={'status':'in_scope'}), patch.object(pipeline, 'search_recipes', return_value=[self.recipe]), patch.object(pipeline, 'generate_recipe') as generate, patch.object(pipeline, 'evaluate_generation', return_value='{"result":"PASS","explanation":"ok","violations":[]}') as judge:
            result = pipeline.run_nosh(self.pantry)
        self.assertEqual(result['status'], 'ok')
        generate.assert_not_called()
        judge.assert_called_once()

    def test_inventory_uses_replacement_quantities(self):
        lines = build_inventory_ingredients(self.recipe, self.plan)
        self.assertIn("15 tablespoon milk", lines)
        self.assertIn("1 tablespoon lemon juice", lines)
        self.assertFalse(any("buttermilk" in line for line in lines))
        self.assertIn("¾ cup white sugar", lines)

    def test_ambiguous_consumption_requires_manual_inventory_update(self):
        self.recipe['metadata']['ingredients'] = self.recipe['metadata']['ingredients'].replace('1 cup buttermilk', '2 cups buttermilk')
        self.assertIsNone(build_inventory_ingredients(self.recipe, self.plan))

    def test_exact_recipe_keeps_inventory_lines(self):
        self.assertIn("1 cup buttermilk", build_inventory_ingredients(self.recipe, []))
