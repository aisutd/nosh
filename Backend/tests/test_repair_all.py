"""Batch import persistence, resume, and failure isolation without network access."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import URLError

from rag.repair_all import repair_all
from rag.source_import import load_repairs


class BatchRepairTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.csv = root / 'recipes.csv'
        self.repairs = root / 'repairs.json'
        self.report = root / 'report.json'
        self.rows = [dict(recipe_name=name, url=f'https://example.org/{name}',
                          ingredients='old', directions='old') for name in ('A', 'B', 'C')]
        self.write_rows(self.rows + [self.rows[0]])
        self.calls = []
        self.waits = []

    def write_rows(self, rows):
        with self.csv.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def fetch(self, url):
        self.calls.append(url)
        return '<script type="application/ld+json">' + json.dumps({
            '@type': 'Recipe', 'name': url.rsplit('/', 1)[-1],
            'recipeIngredient': ['1 cup flour', '1 cup milk'],
            'recipeInstructions': ['Mix.', 'Bake.']}) + '</script>'

    def run_batch(self, **kwargs):
        return repair_all(self.csv, repairs_path=self.repairs, report_path=self.report,
                          sleeper=self.waits.append, **kwargs)

    def test_unique_sources_preview_and_rate_limit(self):
        report = self.run_batch(fetcher=self.fetch)
        self.assertEqual(report['counts'], {'preview': 3})
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.waits, [2.0, 2.0])
        self.assertFalse(self.repairs.exists())
        self.assertTrue(report['complete'])
        self.run_batch(apply=True, fetcher=self.fetch)
        self.assertEqual(len(load_repairs(self.repairs)), 3)

    def test_interrupted_run_checkpoints_and_resumes(self):
        def interrupted(url):
            if url.endswith('/B'):
                raise KeyboardInterrupt()
            return self.fetch(url)
        with self.assertRaises(KeyboardInterrupt):
            self.run_batch(apply=True, fetcher=interrupted)
        self.assertEqual(len(load_repairs(self.repairs)), 1)
        self.assertFalse(json.loads(self.report.read_text())['complete'])
        self.calls.clear()
        report = self.run_batch(apply=True, fetcher=self.fetch)
        self.assertEqual(report['counts'], {'skipped': 1, 'updated': 2})
        self.assertEqual(self.calls, [r['url'] for r in self.rows[1:]])

    def test_failure_does_not_stop_batch_and_retries_next_run(self):
        def blocked(url):
            if url.endswith('/B'):
                raise URLError('blocked')
            return self.fetch(url)
        report = self.run_batch(apply=True, fetcher=blocked)
        self.assertEqual(report['counts'], {'updated': 2, 'unverified': 1})
        self.calls.clear()
        self.run_batch(apply=True, fetcher=self.fetch)
        self.assertEqual(self.calls, [self.rows[1]['url']])
        before = self.repairs.read_bytes()
        self.run_batch(apply=True, refresh=True, fetcher=blocked)
        self.assertEqual(self.repairs.read_bytes(), before)

    def test_limit_and_conflicting_titles(self):
        report = self.run_batch(apply=True, limit=1, fetcher=self.fetch)
        self.assertFalse(report['complete'])
        self.assertEqual(len(self.calls), 1)
        self.write_rows([self.rows[0], {**self.rows[0], 'recipe_name': 'Wrong title'}])
        self.calls.clear()
        report = self.run_batch(apply=True, fetcher=self.fetch)
        self.assertEqual(report['counts'], {'unverified': 1})
        self.assertEqual(self.calls, [])

    def test_invalid_options_cannot_overwrite_data(self):
        for kwargs in ({'delay': -1}, {'delay': float('nan')}, {'limit': 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_batch(**kwargs)
        with self.assertRaises(ValueError):
            repair_all(self.csv, repairs_path=self.repairs, report_path=self.csv)
