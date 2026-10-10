"""Run with python -m unittest discover -s tests -v (real MiniLM + Chroma)."""
import contextlib
import csv
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rag.build_embeddings import build_index, load_records, parse_minutes
from rag.store import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, client_for
from retrieval.nosh_retrieval import (
    get_collection, search_recipes, retrieve_candidate_recipes, format_recipes_for_llm,
)


class DataTests(unittest.TestCase):
    def test_duration_parsing(self):
        for raw, expected in [('1 hrs 15 mins', 75), ('2 days 3 hours 5 minutes', 3065),
                              ('10 mins', 10), ('', None), ('unknown', None),
                              ('1 hr overnight', None)]:
            with self.subTest(raw=raw):
                self.assertEqual(parse_minutes(raw), expected)

    def test_dataset_deduplicated_and_source_preserved(self):
        records, rows = load_records(DEFAULT_CSV_PATH)
        self.assertEqual(rows, 1090)
        self.assertEqual(len(records), 961)
        for document, meta in records.values():
            self.assertIn(meta['ingredients'], document)
            self.assertIn(meta['directions'], document)
            self.assertEqual(meta['title'], meta['recipe_name'])

    def test_invalid_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'invalid.csv'
            path.write_text('title\nSoup\n')
            with self.assertRaisesRegex(ValueError, 'CSV must contain'):
                load_records(path)

    def test_invalid_requests_before_database_access(self):
        for query, k in [('', 5), ('  ', 5), ('soup', 0), ('soup', -1), ('soup', True), ('soup', 1.5)]:
            with self.subTest(query=query, k=k), self.assertRaises(ValueError):
                search_recipes(query, k)
        for limit in [-1, float('nan'), float('inf'), True, '10']:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                search_recipes('soup', max_time=limit)
        for kwargs in [{'dietary_pref': 'vegan'}]:
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                retrieve_candidate_recipes('soup', **kwargs)


class ChromaIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name)
        wanted = {'Old-Fashioned Lemonade', 'Coconut Rice', 'Fresh Mango Salsa',
                  'Baked Salmon in Foil', 'Peanut Butter Banana Smoothie',
                  'Apple-Cranberry Crostada', 'Avocado Toast with Egg'}
        with DEFAULT_CSV_PATH.open(newline='') as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames
            unique = {r['url']: r for r in reader if r['recipe_name'] in wanted}
        cls.rows = list(unique.values())
        cls.csv_path = cls.path / 'recipes.csv'
        cls.write_csv(cls.rows + [cls.rows[0]])
        with contextlib.redirect_stdout(io.StringIO()):
            cls.summary = build_index(cls.csv_path, cls.path / 'db', batch_size=3)
        cls.collection = get_collection(cls.path / 'db')

    @classmethod
    def write_csv(cls, rows):
        with cls.csv_path.open('w', newline='') as output:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_semantic_top_k_and_metadata(self):
        results = search_recipes('a refreshing drink with lemons sugar and water', 3,
                                 collection=self.collection)
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['title'], 'Old-Fashioned Lemonade')
        self.assertEqual([r['distance'] for r in results], sorted(r['distance'] for r in results))
        self.assertEqual(len({r['url'] for r in results}), 3)
        for r in results:
            self.assertTrue(r['ingredients'])
            self.assertTrue(r['directions'])
            self.assertAlmostEqual(r['similarity'], 1 - r['distance'])

    def test_k_larger_than_index(self):
        self.assertEqual(len(search_recipes('food', 100, collection=self.collection)), len(self.rows))

    def test_strict_time_filter_and_unknown_excluded(self):
        results = search_recipes('fruit', 100, max_time=15, collection=self.collection)
        self.assertTrue(results)
        self.assertTrue(all(r['metadata']['total_time_minutes'] <= 15 for r in results))
        self.assertNotIn('Apple-Cranberry Crostada', [r['title'] for r in results])
        self.assertEqual(search_recipes('food', max_time=0, collection=self.collection), [])

    def test_available_ingredients_filter_and_time(self):
        results = search_recipes('salmon dinner', 1, collection=self.collection,
                                 available_ingredients=['lemons', 'sugar'])
        self.assertEqual([r['title'] for r in results], ['Old-Fashioned Lemonade'])
        self.assertEqual(results[0]['rank'], 1)
        self.assertEqual(search_recipes('lemonade', collection=self.collection,
                                       available_ingredients=['lemon']), [])
        self.assertEqual(search_recipes('lemonade', collection=self.collection,
                                       available_ingredients=[], max_time=15), [])
        self.assertEqual(search_recipes('lemonade', collection=self.collection,
                                       available_ingredients=['lemon', 'sugar'], max_time=0), [])

    def test_missing_ingredients_skip_generation(self):
        import nosh_pipeline
        with patch.object(nosh_pipeline, 'classify_request', return_value={'status': 'in_scope'}), \
                patch.object(nosh_pipeline, 'generate_recipe') as generate:
            result = nosh_pipeline.run_nosh(['lemon'], collection=self.collection)
        self.assertEqual(result['status'], 'no_recipes_found')
        generate.assert_not_called()

    def test_empty_collection(self):
        empty = client_for(self.path / 'db').create_collection('empty_test')
        self.assertEqual(search_recipes('fruit', collection=empty), [])

    def test_reopen_persistence(self):
        from retrieval.nosh_retrieval import _open_collection
        _open_collection.cache_clear()
        reopened = get_collection(self.path / 'db')
        self.assertEqual(reopened.count(), len(self.rows))
        self.assertEqual(search_recipes('Coconut Rice', 1, collection=reopened)[0]['title'], 'Coconut Rice')

    def test_missing_and_incompatible_index(self):
        with self.assertRaisesRegex(RuntimeError, 'index not found'):
            get_collection(self.path / 'missing')
        client_for(self.path / 'db').create_collection('old_index')
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            get_collection(self.path / 'db', 'old_index')

    def test_default_path_independent_of_cwd(self):
        from retrieval.nosh_retrieval import _open_collection
        original = Path.cwd()
        try:
            os.chdir(self.path)
            with patch('retrieval.nosh_retrieval._open_collection') as opened:
                get_collection()
                opened.assert_called_once_with(str(DEFAULT_DB_PATH), 'recipes')
        finally:
            os.chdir(original)

    def test_context_preserves_source(self):
        recipes = search_recipes('Mango salsa', 2, collection=self.collection)
        context = format_recipes_for_llm(recipes, top_k=2)
        for r in recipes:
            self.assertIn(r['document'], context)
            self.assertIn(r['url'], context)

    def test_z_rebuild_idempotent_and_removes_stale(self):
        with contextlib.redirect_stdout(io.StringIO()):
            summary = build_index(self.csv_path, self.path / 'db')
        self.assertEqual(summary['unique_recipes'], len(self.rows))
        self.write_csv(self.rows[:-1])
        with contextlib.redirect_stdout(io.StringIO()):
            summary = build_index(self.csv_path, self.path / 'db')
        self.assertEqual(summary['unique_recipes'], len(self.rows) - 1)

    def test_pipeline_passes_semantic_result_to_generation(self):
        import nosh_pipeline
        with patch.object(nosh_pipeline, 'classify_request', return_value={'status': 'in_scope'}), \
                patch.object(nosh_pipeline, 'evaluate_generation', return_value='{"result":"PASS","explanation":"Supported","violations":[]}'), \
                patch.object(nosh_pipeline, 'generate_recipe', return_value='generated') as generate:
            result = nosh_pipeline.run_nosh(['lemon', 'sugar', 'water'],
                                            collection=self.collection, top_k=3)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['source_recipe'], 'Old-Fashioned Lemonade')
        generate.assert_called_once()
        self.assertEqual(generate.call_args.kwargs['available_ingredients'], 'lemon, sugar')
        self.assertEqual(generate.call_args.kwargs['retrieved_context'],
                         format_recipes_for_llm(result['recipes'], top_k=1))
        self.assertEqual(len(result['recipes']), 1)
        self.assertEqual(result['recipe'], 'generated')
        self.assertEqual(result['source_url'], result['recipes'][0]['url'])
        self.assertIn('similarity', result)
        # Model boundaries are mocked; retrieval above is real Chroma + MiniLM.

    def test_pipeline_skips_llm_for_empty_input(self):
        import nosh_pipeline
        with patch.object(nosh_pipeline, 'generate_recipe') as generate, \
                patch.object(nosh_pipeline, 'search_recipes') as search:
            result = nosh_pipeline.run_nosh([])
        self.assertEqual(result['status'], 'no_ingredients')
        generate.assert_not_called()
        search.assert_not_called()

    def test_pipeline_skips_llm_when_time_filter_has_no_matches(self):
        import nosh_pipeline
        with patch.object(nosh_pipeline, 'classify_request', return_value={'status': 'in_scope'}), \
                patch.object(nosh_pipeline, 'generate_recipe') as generate:
            result = nosh_pipeline.run_nosh('lemon, sugar', max_time=0,
                                            collection=self.collection)
        self.assertEqual(result['status'], 'no_recipes_found')
        self.assertEqual(result['recipes'], [])
        generate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
