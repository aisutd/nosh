"""Offline tests for near-match recommendations and cooking restrictions."""
import os
import unittest
from unittest.mock import MagicMock, patch

import nosh_pipeline as pipeline
from retrieval.availability import assess_availability, recommendation_threshold
from retrieval.ingredients import normalize_available, matches_available
from retrieval.nosh_retrieval import search_recipes
from retrieval.hybrid_search import hybrid_search_recipes, _bm25_search


def inventory(raw):
    return normalize_available(raw, semantic=False)


# Ten distinct requirements; these fixtures never enter application data.
INGREDIENTS = "flour, sugar, egg, butter, milk, apple, cinnamon, vanilla, oat, walnut"
PANTRY = INGREDIENTS.rsplit(",", 1)[0]


def recipe(rid, raw):
    return {"id": rid, "title": rid, "metadata": {"ingredients": raw},
            "document": f"Ingredients: {raw}", "ingredients": raw}


class AvailabilityTests(unittest.TestCase):
    def test_threshold_and_staples(self):
        raw = INGREDIENTS + ", salt, water, black pepper"
        profile = assess_availability(raw, inventory(PANTRY))
        self.assertEqual(profile["coverage"], .9)
        self.assertEqual(profile["pantry_match"], .9)
        self.assertEqual(profile["unresolved_ingredients"], ["walnut"])
        self.assertEqual(len(profile["required_ingredients"]), 10)
        self.assertFalse(profile["ready_to_cook"])
        self.assertTrue(matches_available(raw, inventory(PANTRY), min_coverage=.9))
        self.assertFalse(matches_available(raw, inventory(PANTRY), min_coverage=.95))
        self.assertFalse(matches_available(raw, inventory(PANTRY)))
        # One absent ingredient among twenty meets 95% exactly.
        twenty = raw + ", pear, peach, plum, rice, salmon, garlic, onion, carrot, celery, spinach"
        nineteen = PANTRY + ", pear, peach, plum, rice, salmon, garlic, onion, carrot, celery, spinach"
        self.assertEqual(assess_availability(twenty, inventory(nineteen))["coverage"], .95)
        self.assertTrue(matches_available(twenty, inventory(nineteen), min_coverage=.95))

    def test_partial_substitutions_keep_unresolved_gaps(self):
        profile = assess_availability("buttermilk, flour, walnut", inventory("milk, lemon, flour"))
        self.assertEqual(profile["available_ingredients"], ["flour"])
        self.assertEqual(profile["missing_ingredients"], ["buttermilk", "walnut"])
        self.assertEqual(profile["unresolved_ingredients"], ["walnut"])
        self.assertEqual(profile["pantry_match"], 1/3)
        self.assertEqual(profile["coverage"], 2/3)
        self.assertEqual(profile["substitutions"][0]["replacement_ingredients"], ["milk", "lemon"])
        incomplete = assess_availability("buttermilk", inventory("milk"))
        self.assertEqual(incomplete["coverage"], 0)
        self.assertEqual(incomplete["substitutions"], [])

    def test_unknown_and_empty_fail_closed(self):
        for raw in ("", None):
            self.assertIsNone(assess_availability(raw, inventory(PANTRY)))
        self.assertEqual(assess_availability("unknown food", inventory(PANTRY))["coverage"], 0)
        self.assertEqual(assess_availability("water, salt", inventory(PANTRY))["coverage"], 1)

    def test_config_validation(self):
        for value in ("nan", "inf", "0", "-1", "1.1", "invalid"):
            with self.subTest(value=value), patch.dict(os.environ, NOSH_MIN_RECIPE_COVERAGE=value):
                with self.assertRaises(ValueError):
                    recommendation_threshold()
        with patch.dict(os.environ, NOSH_MIN_RECIPE_COVERAGE="0.95"):
            self.assertEqual(recommendation_threshold(), .95)

    def test_options_allow_near_matches_but_generation_does_not(self):
        near = recipe("near", INGREDIENTS)
        collection = MagicMock()
        collection.get.return_value = {"ids": ["near"], "metadatas": [near["metadata"]], "documents": [near["document"]]}
        with patch.object(pipeline, "classify_request", return_value={"status": "in_scope"}), patch.object(pipeline, "search_recipes", return_value=[near]), patch.object(pipeline, "generate_recipe") as generate, patch.object(pipeline, "evaluate_generation") as judge, patch.dict(os.environ, NOSH_MIN_RECIPE_COVERAGE="0.9"):
            options = pipeline.run_nosh(PANTRY, retrieve_only=True)
            self.assertEqual(options["status"], "ok")
            self.assertEqual(options["recipes"][0]["availability"]["coverage"], .9)
            self.assertEqual(pipeline.run_nosh(PANTRY)["status"], "no_recipes_found")
            selected = pipeline.run_nosh(PANTRY, selected_recipe_id="near", collection=collection)
            self.assertEqual(selected["status"], "ingredients_changed")
            self.assertIsNone(selected["recipe"])
            self.assertEqual(selected["recipes"][0]["availability"]["unresolved_ingredients"], ["walnut"])
            self.assertNotIn("inventory_ingredients", selected)
            generate.assert_not_called()
            judge.assert_not_called()

    def test_vector_ranks_coverage_before_limit(self):
        collection = MagicMock()
        collection.count.return_value = 3
        collection.query.return_value = {
            "ids": [["near", "too-far", "exact"]],
            "documents": [["Near", "Far", "Exact"]],
            "metadatas": [[{"ingredients": INGREDIENTS}, {"ingredients": INGREDIENTS + ", pear"}, {"ingredients": PANTRY}]],
            "distances": [[.1, .2, .3]],
        }
        results = search_recipes("muffins", top_k=2, collection=collection, available_ingredients=PANTRY, min_coverage=.9)
        self.assertEqual([r["id"] for r in results], ["exact", "near"])

    def test_bm25_ranks_coverage_before_limit(self):
        collection = MagicMock()
        model = MagicMock()
        model.get_scores.return_value = [3, 2, 1]
        data = (model, ["near", "too-far", "exact"], ["Near", "Far", "Exact"],
                [{"ingredients": INGREDIENTS}, {"ingredients": INGREDIENTS + ", pear"}, {"ingredients": PANTRY}])
        with patch("retrieval.hybrid_search._build_bm25", return_value=data):
            results = _bm25_search("muffins", collection, 2, available=inventory(PANTRY), min_coverage=.9)
        self.assertEqual([r["id"] for r in results], ["exact", "near"])

    def test_hybrid_keeps_coverage_order_after_fusion(self):
        near, exact = recipe("near", INGREDIENTS), recipe("exact", PANTRY)
        for r in (near, exact):
            r.update(distance=.1, similarity=.9)
        with patch("retrieval.hybrid_search.search_recipes", return_value=[near, exact]) as vector, patch("retrieval.hybrid_search._bm25_search", return_value=[near]) as keyword:
            results = hybrid_search_recipes("muffins", top_k=1, collection=MagicMock(), available_ingredients=PANTRY, min_coverage=.9)
        self.assertEqual(results[0]["id"], "exact")
        self.assertEqual(vector.call_args.kwargs["min_coverage"], .9)
        self.assertEqual(keyword.call_args.kwargs["min_coverage"], .9)
