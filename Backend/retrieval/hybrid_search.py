"""Hybrid BM25 + vector search with Reciprocal Rank Fusion reranking.

Combines keyword (BM25) and semantic (ChromaDB) search results so that recipes
matching both the query words and the meaning rank highest.

Usage:
    from retrieval.hybrid_search import hybrid_search_recipes
    recipes = hybrid_search_recipes("lemon garlic salmon", top_k=5,
                                    available_ingredients="salmon, lemon, garlic")
"""
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from rag.store import DEFAULT_DB_PATH, COLLECTION_NAME
from retrieval.nosh_retrieval import (
    get_collection,
    search_recipes,
    normalize_ingredients,
)
from retrieval.ingredients import normalize_available, matches_available

# Reciprocal Rank Fusion constant — higher k reduces the impact of top ranks.
_RRF_K = 60


def _tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric characters for BM25."""
    return re.findall(r"[a-z0-9]+", text.lower())


_bm25_cache: dict = {}


def _build_bm25(cache_key: str, collection):
    """Build and cache a BM25 index from all documents in the collection.

    The index is keyed by cache_key (collection name + doc count) so rebuilding
    the Chroma index automatically invalidates the cache.
    """
    if cache_key in _bm25_cache:
        return _bm25_cache[cache_key]

    data = collection.get(include=["documents", "metadatas"])
    ids = data["ids"]
    documents = data["documents"]
    metadatas = data["metadatas"]

    tokenized = [_tokenize(doc) for doc in documents]
    bm25 = BM25Okapi(tokenized)

    _bm25_cache[cache_key] = (bm25, ids, documents, metadatas)
    return _bm25_cache[cache_key]


def _bm25_search(query: str, collection, top_n: int, available=None, max_time=None):
    """Run BM25 keyword search and return ranked results filtered to constraints."""
    # Use the collection count as a stable cache key proxy
    cache_key = f"{collection.name}:{collection.count()}"
    bm25, ids, documents, metadatas = _build_bm25(cache_key, collection)

    query_tokens = _tokenize(query)
    scores = bm25.get_scores(query_tokens)

    # Pair each doc with its score and metadata, then sort descending
    ranked = sorted(
        zip(scores, ids, documents, metadatas),
        key=lambda x: x[0],
        reverse=True,
    )

    results = []
    for score, rid, document, metadata in ranked:
        if score <= 0:
            break
        metadata = metadata or {}
        if max_time is not None:
            doc_time = metadata.get("total_time_minutes")
            if doc_time is None or doc_time > max_time:
                continue
        if available is not None:
            if not matches_available(metadata.get("ingredients", ""), available):
                continue
        results.append({
            "id": rid,
            "document": document,
            "metadata": metadata,
            "bm25_score": float(score),
        })
        if len(results) >= top_n:
            break

    return results


def _reciprocal_rank_fusion(
    vector_results: list[dict],
    bm25_results: list[dict],
    k: int = _RRF_K,
) -> list[dict]:
    """Merge two ranked lists using Reciprocal Rank Fusion.

    Each document scores 1/(k + rank) per list it appears in; scores are summed.
    Documents appearing in both lists rank higher than those in just one.
    """
    rrf_scores: dict[str, float] = {}
    doc_data: dict[str, dict] = {}

    for rank, result in enumerate(vector_results, 1):
        rid = result["id"]
        rrf_scores[rid] = rrf_scores.get(rid, 0.0) + 1.0 / (k + rank)
        doc_data[rid] = result

    for rank, result in enumerate(bm25_results, 1):
        rid = result["id"]
        rrf_scores[rid] = rrf_scores.get(rid, 0.0) + 1.0 / (k + rank)
        if rid not in doc_data:
            doc_data[rid] = result

    merged = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {**doc_data[rid], "rrf_score": score}
        for rid, score in merged
    ]


def hybrid_search_recipes(
    query: str,
    top_k: int = 5,
    *,
    max_time=None,
    collection=None,
    available_ingredients=None,
    db_path=DEFAULT_DB_PATH,
    collection_name: str = COLLECTION_NAME,
    bm25_candidates: int = 50,
) -> list[dict]:
    """Return top-k recipes using hybrid BM25 + vector search with RRF reranking.

    Drop-in replacement for retrieval.nosh_retrieval.search_recipes().
    Returns the same field structure so the rest of the pipeline is unchanged.

    Args:
        query: Free-text cooking request.
        top_k: Number of results to return.
        max_time: Maximum total recipe time in minutes.
        collection: Existing Chroma collection (opened if not supplied).
        available_ingredients: Comma-separated string or list of available ingredients.
        db_path: Path to the Chroma database.
        collection_name: Name of the Chroma collection.
        bm25_candidates: How many BM25 candidates to fetch before filtering.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a nonempty string")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    if collection is None:
        collection = get_collection(db_path, collection_name)

    available = (
        normalize_available(available_ingredients)
        if available_ingredients is not None
        else None
    )

    # --- Vector search (semantic) ---
    # Fetch more candidates than top_k to give RRF enough to work with.
    vector_raw = search_recipes(
        query,
        top_k=max(top_k * 4, bm25_candidates),
        max_time=max_time,
        collection=collection,
        available_ingredients=available_ingredients,
    )
    vector_results = [
        {"id": r["id"], "document": r["document"], "metadata": r["metadata"],
         "distance": r["distance"], "similarity": r["similarity"]}
        for r in vector_raw
    ]

    # --- BM25 search (keyword) ---
    bm25_results = _bm25_search(
        query, collection, top_n=bm25_candidates,
        available=available, max_time=max_time,
    )

    # --- Reciprocal Rank Fusion ---
    merged = _reciprocal_rank_fusion(vector_results, bm25_results)

    # --- Format output to match search_recipes() structure ---
    output = []
    for rank, result in enumerate(merged[:top_k], 1):
        metadata = result["metadata"] or {}
        distance = result.get("distance", 1.0 - result.get("rrf_score", 0.0))
        output.append({
            "rank": rank,
            "id": result["id"],
            "title": metadata.get("recipe_name", metadata.get("title", "Untitled")),
            "document": result["document"],
            "metadata": metadata,
            "distance": distance,
            "similarity": result.get("similarity", 1.0 - distance),
            "ingredients": metadata.get("ingredients", ""),
            "directions": metadata.get("directions", ""),
            "url": metadata.get("url", ""),
            "rrf_score": result.get("rrf_score", 0.0),
            "bm25_score": result.get("bm25_score", 0.0),
        })

    return output


def main():
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--ingredients", help="Comma-separated available ingredients")
    parser.add_argument("--max-time", type=float)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    args = parser.parse_args()

    try:
        recipes = hybrid_search_recipes(
            args.query, args.top_k,
            max_time=args.max_time,
            available_ingredients=args.ingredients,
            db_path=args.db_path,
            collection_name=args.collection,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")

    print(json.dumps(
        [{"rank": r["rank"], "title": r["title"], "rrf_score": round(r["rrf_score"], 4),
          "similarity": round(r["similarity"], 4), "url": r["url"]} for r in recipes],
        indent=2,
    ))


if __name__ == "__main__":
    main()
