"""Saved recipes must use today's pantry, including an empty pantry."""
import importlib.util
from pathlib import Path
from types import ModuleType
import sys
import unittest
from unittest.mock import MagicMock, patch

import nosh_pipeline as pipeline


def load_routes():
    # Import the real route without opening MongoDB or loading credentials.
    database = ModuleType("database.configurations")
    database.collection = MagicMock()
    database.user = MagicMock()
    security = ModuleType("security")
    security.get_current_user = lambda: None
    spec = importlib.util.spec_from_file_location(
        "saved_recipe_routes_test", Path(__file__).resolve().parents[1] / "routes/recipes.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"database.configurations": database, "security": security}):
        spec.loader.exec_module(module)
    return module


class SavedPantryTests(unittest.IsolatedAsyncioTestCase):
    async def check_saved(self, current, raw, saved):
        routes = load_routes()
        rid = "a" * 64
        user = {"saved_recipes": ["rag:" + rid], "ingredients": current,
                "rag_contexts": {rid: {"ingredients": saved, "user_query": ""}}}
        collection = MagicMock()
        collection.get.return_value = {"ids": [rid], "documents": [f"Ingredients: {raw}"],
                                       "metadatas": [{"ingredients": raw, "recipe_name": "Test"}]}
        with patch("retrieval.nosh_retrieval.get_collection", return_value=collection), patch.object(pipeline, "classify_request", return_value={"status": "in_scope"}), patch.object(pipeline, "generate_recipe") as generate, patch.object(pipeline, "evaluate_generation") as judge:
            result = (await routes.generate_saved_recipe("rag:" + rid, user))["result"]
            self.assertEqual(result["status"], "ingredients_changed")
            self.assertIsNone(result["recipe"])
            generate.assert_not_called()
            judge.assert_not_called()
        return result["recipes"][0]["availability"]

    async def test_removed_ingredient_is_missing(self):
        profile = await self.check_saved(["flour"], "flour, egg", ["flour", "egg"])
        self.assertEqual(profile["unresolved_ingredients"], ["egg"])

    async def test_removed_replacement_invalidates_substitution(self):
        profile = await self.check_saved(["flour", "milk"], "flour, buttermilk", ["flour", "milk", "lemon"])
        self.assertEqual(profile["unresolved_ingredients"], ["buttermilk"])
        self.assertEqual(profile["substitutions"], [])

    async def test_empty_pantry_never_falls_back_to_saved_snapshot(self):
        profile = await self.check_saved([], "flour, egg", ["flour", "egg"])
        self.assertEqual(profile["unresolved_ingredients"], ["egg", "flour"])
        self.assertEqual(profile["coverage"], 0)

    async def test_new_replacement_is_used(self):
        # Egg remains missing so no model call is needed to inspect the new plan.
        profile = await self.check_saved(["flour", "milk", "lemon"], "flour, buttermilk, egg", ["flour", "buttermilk"])
        self.assertEqual(profile["unresolved_ingredients"], ["egg"])
        self.assertEqual(profile["substitutions"][0]["replacement_ingredients"], ["milk", "lemon"])

    async def test_original_query_is_preserved(self):
        from unittest.mock import AsyncMock
        routes = load_routes()
        user = {"saved_recipes": ["rag:test"], "ingredients": ["flour", "egg"],
                "rag_contexts": {"test": {"ingredients": ["flour"], "user_query": "Make pancakes"}}}
        with patch.object(routes, "run_in_threadpool", new_callable=AsyncMock, return_value={"status": "ok"}) as runner:
            await routes.generate_saved_recipe("rag:test", user)
            self.assertEqual(runner.call_args.args[1], ["flour", "egg"])
            self.assertEqual(runner.call_args.kwargs["user_query"], "Make pancakes")
