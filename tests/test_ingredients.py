import unittest
from retrieval.ingredients import normalize_name, normalize_available, matches_available, required_ingredients


class IngredientTests(unittest.TestCase):
    def test_quantities_preparation_and_aliases(self):
        for raw, expected in [('2 tablespoons olive oil', 'olive oil'),
                              ('3 cloves garlic', 'garlic'), ('1 cup chopped tomatoes', 'tomato'),
                              ('½ cup white sugar', 'sugar'), ('2 eggs', 'egg'),
                              ('asparagus', 'asparagus')]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_name(raw), expected)
        self.assertEqual(required_ingredients('3 cloves garlic, minced, 2 tomatoes, peeled, chopped'),
                         {'garlic', 'tomato'})

    def test_no_substring_or_implicit_substitutions(self):
        available = normalize_available('milk, butter, pepper, rice')
        for required in ['1 cup coconut milk', '1 cup peanut butter', '1 bell pepper', '1 cup rice vinegar']:
            with self.subTest(required=required):
                self.assertFalse(matches_available(required, available))

    def test_pantry_unknown_and_missing_data(self):
        available = normalize_available('lemon, sugar')
        self.assertTrue(matches_available('6 lemons, 1 cup white sugar, 6 cups water, or more as needed', available))
        self.assertTrue(matches_available('sea salt to taste, ground black pepper to taste', available))
        for raw in [None, '', '1 cup mystery sauce', '1 tablespoon oil', '1 teaspoon butter']:
            with self.subTest(raw=raw):
                self.assertFalse(matches_available(raw, available))
        for invalid in [42, {'lemon'}, ['lemon', 1]]:
            with self.assertRaises(ValueError):
                normalize_available(invalid)
