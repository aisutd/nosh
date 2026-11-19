"""Catalog completeness, context restrictions and real-corpus coverage."""
import csv
import unittest
from pathlib import Path
from unittest.mock import patch
from retrieval import substitutions
from retrieval.ingredients import normalize_available, required_ingredients


class CatalogTests(unittest.TestCase):
    def test_every_alternative_requires_each_nonpantry_component(self):
        for ingredient, alternatives in substitutions.CATALOG.items():
            for option in alternatives:
                with self.subTest(id=option["id"]):
                    context = "salad dressing" if ingredient == "mayonnaise" else "bake oven soup sauce minced garlic"
                    components = {c["ingredient"] for c in option["components"]}
                    with patch.object(substitutions, "CATALOG", {ingredient: [option]}):
                        plan = substitutions.plan_substitutions(ingredient, components, context=context)
                        self.assertIsNotNone(plan)
                        self.assertEqual(plan[0]["catalog_id"], option["id"])
                        for missing in components:
                            self.assertIsNone(substitutions.plan_substitutions(ingredient, components - {missing}, context=context))

    def test_baking_cream_cannot_be_used_for_whipped_cream(self):
        pantry = normalize_available("milk, butter", semantic=False)
        self.assertIsNotNone(substitutions.plan_substitutions("heavy cream", pantry, context="Bake cake in oven"))
        for context in ("", "Whip cream to stiff peaks for the baked cake", "Make ice cream"):
            self.assertIsNone(substitutions.plan_substitutions("heavy cream", pantry, context=context))

    def test_thickener_and_dressing_scope(self):
        self.assertIsNone(substitutions.plan_substitutions("cornstarch", {"flour"}, context="Coat chicken and fry"))
        self.assertIsNotNone(substitutions.plan_substitutions("cornstarch", {"flour"}, context="Thicken the sauce"))
        self.assertIsNone(substitutions.plan_substitutions("mayonnaise", {"plain yogurt"}, context="Bake a cake"))
        self.assertIsNotNone(substitutions.plan_substitutions("mayonnaise", {"plain yogurt"}, context="Mix salad dressing"))

    def test_no_new_synthetic_inventory_from_chained_substitutions(self):
        # Water + evaporated milk could replace milk, but not recursively inside buttermilk.
        pantry = normalize_available("evaporated milk, lemon", semantic=False)
        self.assertIsNone(substitutions.plan_substitutions("buttermilk", pantry))

    def test_actual_recipe_inventory_can_replace_one_supported_requirement(self):
        count = 0
        path = Path(__file__).resolve().parents[1] / "data/processed/cleaned_recipes.csv"
        with path.open() as source:
            for recipe in csv.DictReader(source):
                required = required_ingredients(recipe["ingredients"]) or set()
                for missing in required & substitutions.CATALOG.keys():
                    for option in substitutions.CATALOG[missing]:
                        components = {c["ingredient"] for c in option["components"]}
                        available = (required - {missing}) | components
                        plan = substitutions.plan_substitutions(recipe["ingredients"], available, context=recipe["recipe_name"] + " " + recipe["directions"])
                        if plan:
                            self.assertNotIn(missing, available)
                            self.assertTrue(all(set(s["replacement_ingredients"]) <= available for s in plan))
                            count += 1
        self.assertGreater(count, 300)
