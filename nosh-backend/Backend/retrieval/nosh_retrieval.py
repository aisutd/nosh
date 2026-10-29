import re

from retrieval.ingredients import normalize_available, matches_available

IGNORED = {"water", "salt", "pepper", "black pepper"}  # always allowed, never counted

from functools import lru_cache
from pathlib import Path

from rag.store import (
    COLLECTION_NAME, DEFAULT_DB_PATH, client_for, embedding_function,
    validate_collection,
)


@lru_cache(maxsize=8)
def _open_collection(path, name):
    from chromadb.errors import NotFoundError
    client = client_for(path)
    try:
        collection = client.get_collection(name=name, embedding_function=None)
    except NotFoundError as exc:
        raise RuntimeError(
            "Recipe index not found. Run `python -m rag.build_embeddings` first "
            "(use the same --db-path and --collection if customized)."
        ) from exc
    validate_collection(collection)
    return client.get_collection(name=name, embedding_function=embedding_function())


def get_collection(path=DEFAULT_DB_PATH, name=COLLECTION_NAME):
    """Open the shared persistent index, independent of working directory."""
    return _open_collection(str(Path(path).expanduser().resolve()), name)


# ---------- Ingredient cleaning ----------

def normalize_ingredient(ing: str) -> str:
    """Lowercase, trim, and crudely singularize ('Tomatoes' -> 'tomato')."""
    ing = re.sub(r"\s+", " ", ing.strip().lower())
    if ing.endswith("ies") and len(ing) > 4:
        return ing[:-3] + "y"
    if ing.endswith("oes"):
        return ing[:-2]
    if ing.endswith("s") and not ing.endswith(("ss", "us")) and len(ing) > 3:
        return ing[:-1]
    return ing


def normalize_ingredients(ings) -> list:
    """Accepts a list or comma-separated string. Drops water/salt/pepper and duplicates."""
    if isinstance(ings, str):
        ings = ings.split(",")
    out = []
    for i in ings:
        n = normalize_ingredient(i)
        if n and n not in IGNORED and n not in out:
            out.append(n)
    return out


def parse_recipe_ingredients(raw) -> list:
    """Chroma metadata can't store lists, so ingredients arrive as 'a, b, c'."""
    return normalize_ingredients(raw if raw else [])


# ---------- Retrieval ----------

def retrieve_candidate_recipes(
    user_query: str,
    dietary_pref: str = None,
    max_time: int = None,
    top_n: int = 20,
    collection=None,
    available_ingredients=None,
):
    """Return Chroma results in semantic order. max_time means TOTAL minutes."""
    if not isinstance(user_query, str) or not user_query.strip():
        raise ValueError("user_query must be a nonempty string")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")
    if dietary_pref is not None:
        raise ValueError("Dietary filters are unavailable: the dataset has no verified dietary labels.")
    if max_time is not None:
        import math
        if (isinstance(max_time, bool) or not isinstance(max_time, (int, float))
                or not math.isfinite(max_time) or max_time < 0):
            raise ValueError("max_time must be a finite nonnegative number of minutes")
    available = (normalize_available(available_ingredients)
                 if available_ingredients is not None else None)
    if collection is None:
        collection = get_collection()
    count = collection.count()
    if count == 0:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    kwargs = {}
    if max_time is not None:
        kwargs["where"] = {"total_time_minutes": {"$lte": max_time}}
    results = collection.query(
        query_texts=[user_query.strip()], n_results=count if available is not None else min(top_n, count),
        include=["documents", "metadatas", "distances"], **kwargs,
    )
    if available is not None:
        keep = [i for i, meta in enumerate(results["metadatas"][0])
                if matches_available((meta or {}).get("ingredients"), available)][:top_n]
        for key in ("ids", "documents", "metadatas", "distances"):
            results[key] = [[results[key][0][i] for i in keep]]
    return results


def search_recipes(query, top_k=5, *, max_time=None, collection=None, available_ingredients=None):
    """Top-k nearest recipes. Lower cosine distance means a closer match.

    Returns full source text and metadata for generation, without an LLM call.
    Similarity is 1 - cosine distance, not a probability or dietary guarantee.
    """
    results = retrieve_candidate_recipes(
        query, max_time=max_time, top_n=top_k, collection=collection,
        available_ingredients=available_ingredients
    )
    recipes = []
    for rank, (rid, document, metadata, distance) in enumerate(zip(
        results["ids"][0], results["documents"][0],
        results["metadatas"][0], results["distances"][0],
    ), 1):
        metadata = metadata or {}
        recipes.append({
            "rank": rank, "id": rid,
            "title": metadata.get("recipe_name", metadata.get("title", "Untitled")),
            "document": document, "metadata": metadata,
            "distance": float(distance), "similarity": 1.0 - float(distance),
            "ingredients": metadata.get("ingredients", ""),
            "directions": metadata.get("directions", ""),
            "url": metadata.get("url", ""),
        })
    return recipes


def rank_by_ingredient_overlap(retrieved_results, available_ingredients):
    user_ings = set(normalize_ingredients(available_ingredients))

    documents = retrieved_results["documents"][0]
    metadatas = retrieved_results["metadatas"][0]
    ids = retrieved_results["ids"][0]
    distances = retrieved_results.get("distances", [[0.0] * len(ids)])[0]

    scored = []
    for doc, meta, rid, dist in zip(documents, metadatas, ids, distances):
        recipe_ings = set(parse_recipe_ingredients(meta.get("ingredients", "")))
        matched = user_ings & recipe_ings
        overlap = len(matched) / max(len(recipe_ings), 1)
        scored.append({
            "id": rid,
            "document": doc,
            "metadata": meta,
            "recipe_ingredients": sorted(recipe_ings),
            "overlap_score": overlap,
            "distance": dist,
        })

    # Best overlap first; ties broken by semantic closeness
    scored.sort(key=lambda r: (-r["overlap_score"], r["distance"]))
    return scored


def format_recipes_for_llm(scored_recipes, top_k=1):
    """Preserve source ingredients and directions instead of reconstructing them."""
    blocks = []
    for i, recipe in enumerate(scored_recipes[:top_k], 1):
        meta = recipe["metadata"]
        title = meta.get("recipe_name", meta.get("title", "Untitled"))
        blocks.append(
            f"Recipe {i}: {title}\n"
            f"Total time: {meta.get('total_time', 'Unknown')}\n"
            f"Source: {meta.get('url', 'Unknown')}\n"
            f"{recipe['document']}"
        )
    return "\n\n".join(blocks)


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Search the team's recipe index by meaning.")
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--ingredients", help="Only return recipes using these comma-separated ingredients plus water, salt and pepper")
    parser.add_argument("--max-time", type=float, help="Maximum total minutes; unknown times excluded")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--collection", default=COLLECTION_NAME)
    args = parser.parse_args()
    try:
        recipes = search_recipes(
            args.query, args.top_k, max_time=args.max_time, available_ingredients=args.ingredients,
            collection=get_collection(args.db_path, args.collection),
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(recipes, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
