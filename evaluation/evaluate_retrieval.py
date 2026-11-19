"""Reproducible small retrieval benchmark; no LLM or generated judgments."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from rag.store import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, MODEL_NAME, COLLECTION_NAME
from retrieval.nosh_retrieval import get_collection, search_recipes

HERE = Path(__file__).resolve().parent


def evaluate(collection, cases, top_k):
    rows = []
    indexed_titles = {m['recipe_name'] for m in collection.get(include=['metadatas'])['metadatas']}
    for case in cases:
        missing = set(case['expected_titles']) - indexed_titles
        if missing:
            raise ValueError(f"Unknown expected titles in {case['id']}: {sorted(missing)}")
        started = time.perf_counter()
        results = search_recipes(case['query'], top_k=top_k,
                                 max_time=case.get('max_time'), collection=collection)
        elapsed = time.perf_counter() - started
        ranks = [r['rank'] for r in results if r['title'] in case['expected_titles']]
        first = min(ranks) if ranks else None
        if case.get('max_time') is not None:
            assert all(r['metadata']['total_time_minutes'] <= case['max_time'] for r in results)
        assert len({r['url'] for r in results}) == len(results)
        rows.append({**case, 'first_relevant_rank': first, 'hit': bool(ranks),
                     'reciprocal_rank': 1 / first if first else 0,
                     'query_seconds': round(elapsed, 4),
                     'results': [{'rank': r['rank'], 'title': r['title'], 'url': r['url'],
                                  'distance': r['distance'], 'similarity': r['similarity']}
                                 for r in results]})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db-path', type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument('--collection', default=COLLECTION_NAME)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--cases', type=Path, default=HERE / 'cases' / 'retrieval_cases.json')
    parser.add_argument('--output-dir', type=Path, default=HERE / 'results')
    args = parser.parse_args()
    collection = get_collection(args.db_path, args.collection)
    rows = evaluate(collection, json.loads(args.cases.read_text()), args.top_k)
    if not rows:
        raise ValueError('At least one evaluation case is required')
    hit_rate = sum(r['hit'] for r in rows) / len(rows)
    mrr = sum(r['reciprocal_rank'] for r in rows) / len(rows)
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
              'model': MODEL_NAME, 'distance_metric': 'cosine', 'python': platform.python_version(),
              'versions': {p: importlib.metadata.version(p) for p in ['chromadb', 'sentence-transformers', 'torch']},
              'indexed_recipes': collection.count(), 'top_k': args.top_k,
              'default_csv_sha256': hashlib.sha256(DEFAULT_CSV_PATH.read_bytes()).hexdigest(),
              'cases_sha256': hashlib.sha256(args.cases.read_bytes()).hexdigest(),
              'hit_rate_at_k': hit_rate, 'mrr_at_k': mrr, 'cases': rows}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'retrieval_results.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Retrieval quality results', '',
             f"Model: `{MODEL_NAME}`. Index: {collection.count()} unique recipes. k = {args.top_k}.", '',
             f"Hit@{args.top_k}: **{hit_rate:.1%}** ({sum(r['hit'] for r in rows)}/{len(rows)} queries). "
             f"MRR@{args.top_k}: **{mrr:.3f}**.", '',
             'Hit@k means at least one predefined relevant recipe appeared in the first k results. '
             'MRR@k averages the reciprocal rank of the first relevant result (zero on a miss).', '',
             'These are 12 small, manually specified development cases, including exact names, '
             'paraphrases, ingredient queries, and a time filter. Expected titles were fixed before '
             'the first evaluation run. They are incomplete relevance labels; these metrics do not '
             'measure precision, dietary safety, generation quality, or performance on unseen users. '
             'The corpus is heavily fruit-focused. Similarity is not calibrated confidence; unrelated '
             'queries still return nearest neighbors. Long chunks may be truncated by the embedding model.', '',
             '| Query | First relevant rank | Top results |', '|---|---:|---|']
    for row in rows:
        titles = '; '.join(r['title'] for r in row['results'])
        lines.append(f"| {row['query']} | {row['first_relevant_rank'] or 'miss'} | {titles} |")
    lines += ['', 'Full ranked results, source URLs, distances, timing, dependency versions, and hashes '
              'are in `retrieval_results.json`. Timing excludes model startup and is not a load test.', '',
              'Reproduce: `python -m evaluation.evaluate_retrieval`', '']
    (args.output_dir / 'retrieval_results.md').write_text('\n'.join(lines))
    print(f"Hit@{args.top_k}: {hit_rate:.1%}; MRR@{args.top_k}: {mrr:.3f}")


if __name__ == '__main__':
    main()
