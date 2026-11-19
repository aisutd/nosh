"""Source import contracts: all groups, no guessing, persistence and indexing."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from rag.source_import import (extract_recipe, SourceImportError, repair_sources,
                               load_repairs, apply_repair)
from rag.build_embeddings import load_records


def page(recipe):
    return '<html><script type="application/ld+json">' + json.dumps(recipe) + '</script></html>'


def source_recipe():
    return {"@type": "Recipe", "name": "Test Tart",
            "recipeIngredient": ["2 cups flour", "1 cup butter", "1/2 cup sugar",
                                 "1 cup cheese", "1 cup sugar", "2 cups berries", "1/2 cup sugar"],
            "recipeInstructions": [
                {"@type": "HowToSection", "name": "Crust", "itemListElement": [
                    {"@type": "HowToStep", "text": "<p>Mix flour &amp; butter.</p>"},
                    {"@type": "HowToStep", "text": "Bake the crust."}]},
                {"@type": "HowToSection", "name": "Filling", "itemListElement": [
                    {"@type": "HowToStep", "text": "Add cheese and sugar."}]},
                {"@type": "HowToStep", "text": "Top with berries."}]}


class SourceImportTests(unittest.TestCase):
    def test_all_groups_preserve_repeated_ingredients(self):
        result = extract_recipe(page(source_recipe()), "Test Tart")
        self.assertEqual(len(result["ingredient_lines"]), 7)
        self.assertEqual(result["ingredient_lines"].count("1/2 cup sugar"), 2)
        self.assertEqual(result["instruction_steps"], ["Mix flour & butter.", "Bake the crust.", "Add cheese and sugar.", "Top with berries."])

    def test_nested_graph_and_grouped_ingredients(self):
        recipe = source_recipe()
        recipe['@type'] = ['Thing', 'https://schema.org/Recipe']
        recipe['recipeIngredient'] = {'@type': 'ItemList', 'itemListElement': [
            {'@type': 'ItemList', 'name': 'Crust', 'itemListElement': ['1 cup flour']},
            {'@type': 'ItemList', 'name': 'Filling', 'itemListElement': ['1 cup cheese']}]}
        result = extract_recipe(page({'@graph': [{'@type': 'WebPage'}, recipe]}), 'Test Tart')
        self.assertEqual(result['ingredient_lines'], ['1 cup flour', '1 cup cheese'])

    def test_unsupported_group_never_imports_partial_recipe(self):
        recipe = source_recipe()
        recipe['recipeIngredient'].append({'@type': 'PropertyValue', 'name': 'Cheese'})
        with self.assertRaises(SourceImportError):
            extract_recipe(page(recipe), 'Test Tart')

    def test_empty_and_incomplete_sources_rejected(self):
        for key in ('recipeIngredient', 'recipeInstructions'):
            recipe = source_recipe()
            recipe[key] = []
            with self.subTest(key=key), self.assertRaises(SourceImportError):
                extract_recipe(page(recipe), 'Test Tart')
        with self.assertRaises(SourceImportError):
            extract_recipe('<html>Access denied</html>', 'Test Tart')

    def test_wrong_or_ambiguous_recipe_rejected(self):
        with self.assertRaises(SourceImportError):
            extract_recipe(page(source_recipe()), 'Other Recipe')
        other = {**source_recipe(), 'recipeIngredient': ['1 cup milk']}
        with self.assertRaises(SourceImportError):
            extract_recipe(page([source_recipe(), other]), 'Test Tart')

    def test_identical_nodes_and_broken_unrelated_json(self):
        html = '<script type="application/ld+json">not json</script>' + page([source_recipe(), source_recipe()])
        self.assertEqual(len(extract_recipe(html, 'Test Tart')['ingredient_lines']), 7)

    def test_simple_text_steps(self):
        recipe = source_recipe()
        recipe['recipeInstructions'] = 'Mix ingredients.\nBake.'
        self.assertEqual(extract_recipe(page(recipe), 'Test Tart')['instruction_steps'], ['Mix ingredients.', 'Bake.'])

    def write_csv(self, path):
        row = {'recipe_name': 'Test Tart', 'ingredients': '2 cups flour',
               'directions': 'Old directions.', 'url': 'https://example.org/tart', 'chunk': 'STALE'}
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(row))
            writer.writeheader()
            writer.writerows([row, row])
        return row

    def test_preview_apply_and_index_integration(self):
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / 'recipes.csv'
            repairs_path = Path(folder) / 'repairs.json'
            row = self.write_csv(csv_path)
            original = csv_path.read_bytes()
            calls = []
            def fetch(url):
                calls.append(url)
                return page(source_recipe())
            urls = [row['url'], row['url']]
            report = repair_sources(csv_path, urls, repairs_path=repairs_path, fetcher=fetch)
            self.assertEqual(report[0]['status'], 'preview')
            self.assertEqual(len(calls), 1)
            self.assertFalse(repairs_path.exists())
            report = repair_sources(csv_path, urls, repairs_path=repairs_path, apply=True, fetcher=fetch)
            self.assertEqual(report[0]['status'], 'updated')
            self.assertEqual(csv_path.read_bytes(), original)
            repairs = load_repairs(repairs_path)
            imported = apply_repair(row, repairs)
            self.assertIn('cheese', imported['ingredients'])
            self.assertNotIn('STALE', imported['chunk'])
            records, count = load_records(csv_path, repairs_path=repairs_path)
            self.assertEqual(count, 2)
            self.assertEqual(len(records), 1)
            document, metadata = next(iter(records.values()))
            self.assertIn('cheese', document)
            self.assertEqual(metadata['ingredients'], imported['ingredients'])
            self.assertEqual(metadata['directions'], imported['directions'])
            before = repairs_path.read_bytes()
            self.assertEqual(repair_sources(csv_path, urls, repairs_path=repairs_path, apply=True, fetcher=fetch)[0]['status'], 'unchanged')
            self.assertEqual(repairs_path.read_bytes(), before)

    def test_failed_fetch_keeps_existing_repair_and_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            csv_path, repairs_path = Path(folder) / 'recipes.csv', Path(folder) / 'repairs.json'
            row = self.write_csv(csv_path)
            repair_sources(csv_path, [row['url']], repairs_path=repairs_path, apply=True,
                           fetcher=lambda url: page(source_recipe()))
            before = repairs_path.read_bytes()
            def blocked(url):
                raise HTTPError(url, 403, 'Forbidden', None, None)
            report = repair_sources(csv_path, [row['url']], repairs_path=repairs_path, apply=True, fetcher=blocked)
            self.assertEqual(report[0]['status'], 'unverified')
            self.assertEqual(repairs_path.read_bytes(), before)
            self.assertIn('403', report[0]['reason'])

    def test_unknown_url_is_not_fetched(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / 'recipes.csv'
            self.write_csv(csv_path)
            fetch = Mock()
            result = repair_sources(csv_path, ['https://example.org/other'], repairs_path=Path(folder) / 'repairs.json', fetcher=fetch)
            self.assertEqual(result[0]['status'], 'unverified')
            fetch.assert_not_called()
