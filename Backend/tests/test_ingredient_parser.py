"""Regression tests for pantry matching; no embeddings or model downloads."""
import unittest
from retrieval.ingredients import normalize_available, required_ingredients, matches_available


class IngredientParserTests(unittest.TestCase):
    def setUp(self):
        self.available = normalize_available(
            ["sugar", "apple", "aubergine", "strawberry", "tomato", "tomato paste",
             "lemon", "orange", "chicken", "pork", "salmon"], semantic=False)

    def test_hulled_strawberries_are_not_an_extra_ingredient(self):
        raw = "2 pounds fresh strawberries, hulled, 4 cups white sugar, ¼ cup lemon juice"
        self.assertEqual(required_ingredients(raw), {"strawberry", "sugar", "lemon"})
        self.assertTrue(matches_available(raw, self.available))

    def test_temperature_qualified_water(self):
        for temperature in ("cold", "warm", "hot"):
            with self.subTest(temperature=temperature):
                self.assertEqual(required_ingredients(f"8 cups {temperature} water"), {"water"})
        self.assertTrue(matches_available(
            "3 lemons, 8 cups cold water, or as needed, 2 cups white sugar, or as needed", self.available))

    def test_preparation_separator_does_not_break_singularization(self):
        for dash in ("-", "–", "—"):
            self.assertEqual(required_ingredients(f"4 apples {dash} peeled, cored and chopped"), {"apple"})

    def test_paired_pantry_seasonings(self):
        self.assertEqual(required_ingredients("salt and pepper to taste"), {"salt", "pepper"})
        self.assertEqual(required_ingredients("salt and ground black pepper to taste"), {"salt", "black pepper"})
        self.assertFalse(matches_available("salt and pepper", {"salt"}))

    def test_real_missing_ingredients_still_block_recipe(self):
        self.assertFalse(matches_available("salmon, lemon, olive oil, rosemary", self.available))
        self.assertFalse(matches_available("apples - peeled, sugar, cinnamon", self.available))

    def test_unrelated_compounds_and_foods_are_preserved(self):
        self.assertEqual(required_ingredients("macaroni and cheese"), {"macaroni and cheese"})
        self.assertEqual(required_ingredients("1 cup cold milk"), {"cold milk"})
        self.assertEqual(required_ingredients("1 cup all-purpose flour"), {"flour"})
        self.assertFalse(matches_available("strawberries, honey", self.available))


if __name__ == "__main__":
    unittest.main()
