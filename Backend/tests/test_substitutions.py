"""Offline substitution contracts: catalog, generation payloads and selected flow."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from retrieval.ingredients import normalize_available, matches_available
from retrieval.substitutions import plan_substitutions
from llm import nosh_generation as llm
import nosh_pipeline as pipeline


def inventory(values):
    return normalize_available(values, semantic=False)


def response(text):
    return SimpleNamespace(message=SimpleNamespace(content=text))


class SubstitutionTests(unittest.TestCase):
    def test_real_apricot_muffins_accepts_complete_pantry(self):
        import csv
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / "data/processed/cleaned_recipes.csv"
        with path.open() as source:
            recipe = next(r for r in csv.DictReader(source) if r["recipe_name"] == "Apricot Muffins")
        available = inventory("dried apricots, flour, sugar, baking soda, butter, vegetable oil, egg, milk, lemon")
        plan = plan_substitutions(recipe["ingredients"], available)
        self.assertIsNotNone(plan)
        self.assertEqual([item["ingredient"] for item in plan], ["buttermilk"])
        self.assertIsNone(plan_substitutions(recipe["ingredients"], available - {"lemon"}))
        self.assertEqual(plan_substitutions(recipe["ingredients"], available | {"buttermilk"}), [])

    def test_harmless_bullets_are_normalized_without_changing_amounts(self):
        raw = "Recipe Name: Muffins\nChanges:\n• none\nSteps:\n1. Use ¾ cup sugar."
        clean = llm.normalize_recipe_format(raw)
        self.assertIn("- none", clean)
        self.assertIn("¾ cup sugar", clean)
        self.assertEqual(llm.output_format_problems(clean), [])

    def test_failed_draft_is_repaired_once_and_revalidated(self):
        recipe = {"id": "test", "title": "Muffins", "url": "", "similarity": 1,
                  "document": "Ingredients: buttermilk", "metadata": {"ingredients": "buttermilk"}}
        fail = '{"result":"FAIL","explanation":"Wrong quantities","violations":["sugar changed"]}'
        passed = '{"result":"PASS","explanation":"ok","violations":[]}'
        for final_verdict, status in [(passed, "ok"), (fail, "failed_validation")]:
            with self.subTest(status=status), patch.object(pipeline, "classify_request", return_value={"status":"in_scope"}), patch.object(pipeline, "search_recipes", return_value=[recipe]), patch.object(pipeline, "generate_recipe", side_effect=["bad draft", "corrected draft"]) as generate, patch.object(pipeline, "evaluate_generation", side_effect=[fail, final_verdict]) as judge:
                result = pipeline.run_nosh("milk, lemon")
                self.assertEqual(result["status"], status)
                self.assertEqual(generate.call_count, 2)
                self.assertEqual(judge.call_count, 2)
                self.assertEqual(generate.call_args.kwargs["repair_feedback"]["validation"], fail)
                self.assertEqual(result["recipe"], "corrected draft" if status == "ok" else None)

    def test_changed_source_quantities_fail_before_judge(self):
        source = "Ingredients: ¾ cup white sugar, ¼ cup melted butter"
        wrong = "Recipe Name: Muffins\nChanges:\n- none\nSteps:\n1. Mix 1/4 cup sugar and 1/2 cup butter."
        with patch.object(llm.ollama, "chat") as chat:
            self.assertFalse(llm.judge_passed(llm.evaluate_generation("sugar, butter", source, wrong)))
            chat.assert_not_called()
        correct = wrong.replace("1/4 cup sugar", "12 tablespoons sugar").replace("1/2 cup butter", "1/4 cup butter")
        self.assertEqual(llm.source_quantity_problems(source, correct, []), [])

    def test_mixed_fractions_reject_changed_amounts_before_judge(self):
        for amount in ("1 1/2", "1½", "1 ½", "1.5", "2 3/4"):
            with self.subTest(amount=amount):
                source = f"Ingredients: {amount} cups flour"
                output = "Recipe Name: Test\nChanges:\n- none\nSteps:\n1. Use 1/4 cup flour."
                with patch.object(llm.ollama, "chat") as chat:
                    self.assertFalse(llm.judge_passed(llm.evaluate_generation("flour", source, output)))
                    chat.assert_not_called()

    def test_fractional_suffix_cannot_mask_wrong_generated_amount(self):
        source = "Ingredients: 1/2 cup flour"
        output = "Recipe Name: Test\nChanges:\n- none\nSteps:\n1. Use 1 1/2 cups flour."
        self.assertTrue(llm.source_quantity_problems(source, output, []))

    def test_mixed_fraction_accepts_equivalent_units_and_multiple_measurements(self):
        for amount in ("1 1/2", "1½", "1 ½", "1.5"):
            source = f"Ingredients: {amount} cups flour, ¼ cup butter"
            output = "Recipe Name: Test\nChanges:\n- none\nSteps:\n1. Mix 24 tablespoons flour and 4 tablespoons butter."
            with self.subTest(amount=amount):
                self.assertEqual(llm.source_quantity_problems(source, output, []), [])

    def test_honey_substitute_requires_granulated_sugar(self):
        for sugar in ("powdered sugar", "icing sugar", "confectioners' sugar", "confectioners’ sugar", "brown sugar", "light brown sugar", "dark brown sugar"):
            with self.subTest(sugar=sugar):
                self.assertIsNone(plan_substitutions("honey", inventory(sugar)))
        for sugar in ("sugar", "white sugar", "granulated sugar"):
            with self.subTest(sugar=sugar):
                self.assertIsNotNone(plan_substitutions("honey", inventory(sugar)))

    def test_sugar_varieties_remain_distinct_for_direct_matching(self):
        for requested, pantry in (("powdered sugar", "sugar"), ("sugar", "powdered sugar"), ("brown sugar", "sugar"), ("sugar", "brown sugar")):
            with self.subTest(requested=requested, pantry=pantry):
                self.assertFalse(matches_available(requested, inventory(pantry)))
        self.assertTrue(matches_available("1 cup confectioners' sugar", inventory("icing sugar")))
        self.assertTrue(matches_available("1 cup packed light brown sugar", inventory("brown sugar")))

    def test_exact_match_has_no_changes(self):
        self.assertEqual(plan_substitutions("1 cup buttermilk", inventory("buttermilk")), [])

    def test_all_components_required(self):
        self.assertIsNone(plan_substitutions("buttermilk", inventory("milk")))
        plan = plan_substitutions("buttermilk", inventory("milk, lemon juice"))
        self.assertEqual(plan[0]["replacement_ingredients"], ["milk", "lemon"])
        self.assertTrue(matches_available("buttermilk", inventory("milk, lemon")))

    def test_plain_yogurt_required(self):
        for name in ("yogurt", "strawberry yogurt", "greek yogurt"):
            self.assertIsNone(plan_substitutions("buttermilk", inventory(name)))
        self.assertEqual(plan_substitutions("buttermilk", inventory("plain yogurt"))[0]["replacement_ingredients"], ["plain yogurt"])

    def test_unknown_missing_and_empty_fail_closed(self):
        for raw in ("buttermilk, egg", "", None):
            self.assertIsNone(plan_substitutions(raw, inventory("milk, lemon")))

    def test_no_recursive_replacements(self):
        self.assertIsNone(plan_substitutions("sour cream", inventory("milk, lemon")))

    def test_baking_powder_requires_three_components(self):
        self.assertIsNone(plan_substitutions("baking powder", inventory("baking soda, cream of tartar")))
        self.assertIsNotNone(plan_substitutions("baking powder", inventory("bicarbonate of soda, cream of tartar, corn starch")))

    def test_generation_and_judge_share_plan(self):
        plan = plan_substitutions("buttermilk", inventory("milk, lemon"))
        output = "Recipe Name: Pancakes\nChanges:\n- buttermilk replaced with milk and lemon\nSteps:\n1. Combine milk and lemon juice."
        with patch.object(llm.ollama, "chat", return_value=response(output)) as chat:
            llm.generate_recipe("milk, lemon", "Pancakes", substitutions=plan)
            self.assertEqual(json.loads(chat.call_args.kwargs["messages"][1]["content"])["substitutions"], plan)
            llm.evaluate_generation("milk, lemon", "Pancakes", output, substitutions=plan)
            self.assertEqual(json.loads(chat.call_args.kwargs["messages"][1]["content"])["substitutions"], plan)

    def test_incomplete_adaptation_never_reaches_judge(self):
        plan = plan_substitutions("buttermilk", inventory("milk, lemon"))
        for changes, step in [("none", "Mix milk and lemon."), ("buttermilk replaced with milk and lemon", "Use buttermilk."), ("buttermilk replaced with milk and lemon", "Use milk.")]:
            output = f"Recipe Name: Pancakes\nChanges:\n- {changes}\nSteps:\n1. {step}"
            with patch.object(llm.ollama, "chat") as chat:
                self.assertFalse(llm.judge_passed(llm.evaluate_generation("milk, lemon", "Pancakes", output, substitutions=plan)))
                chat.assert_not_called()

    def test_selected_recipe_and_options_use_same_plan(self):
        recipe = {"id": "test", "title": "Pancakes", "url": "", "similarity": 1,
                  "document": "Ingredients: buttermilk", "metadata": {"ingredients": "buttermilk", "recipe_name": "Pancakes"}}
        collection = MagicMock()
        collection.get.return_value = {"ids": ["test"], "documents": [recipe["document"]], "metadatas": [recipe["metadata"]]}
        with patch.object(pipeline, "classify_request", return_value={"status": "in_scope"}), patch.object(pipeline, "search_recipes", return_value=[recipe]), patch.object(pipeline, "generate_recipe", return_value="answer") as generate, patch.object(pipeline, "evaluate_generation", return_value='{"result":"PASS","explanation":"ok","violations":[]}') as judge:
            options = pipeline.run_nosh("milk, lemon", retrieve_only=True)
            result = pipeline.run_nosh("milk, lemon", selected_recipe_id="test", collection=collection)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["substitutions"], options["recipes"][0]["substitutions"])
            self.assertEqual(generate.call_args.kwargs["substitutions"], judge.call_args.kwargs["substitutions"])
            blocked = pipeline.run_nosh("milk", selected_recipe_id="test", collection=collection)
            self.assertEqual(blocked["status"], "ingredients_changed")

    def test_search_prefers_exact_match_within_candidates(self):
        def recipe(name, ingredient):
            return {"id": name, "metadata": {"ingredients": ingredient}, "document": name}
        with patch.object(pipeline, "classify_request", return_value={"status": "in_scope"}), patch.object(pipeline, "search_recipes", return_value=[recipe("adapted", "buttermilk"), recipe("exact", "milk")]):
            result = pipeline.run_nosh("milk, lemon", retrieve_only=True)
            self.assertEqual([r["id"] for r in result["recipes"]], ["exact", "adapted"])
