import re

IGNORED = {"water", "salt", "pepper", "black pepper"}  # always allowed, never counted

_collection = None


def get_collection(path: str = "./chroma_db", name: str = "recipes"):
    """Create the Chroma collection once and reuse it."""
    global _collection
    if _collection is None:
        import chromadb  # imported here so the mock test runs without chromadb installed
        client = chromadb.PersistentClient(path=path)
        _collection = client.get_collection(name)
    return _collection


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
    user_budget: float = None,
    top_n: int = 20,
    collection=None,
):
    collection = collection or get_collection()

    # Build filters only for values provided (Chroma's $and needs 2+ conditions)
    conditions = []
    if dietary_pref:
        conditions.append({"dietary_restriction": dietary_pref})
    if max_time is not None:
        conditions.append({"cooking_time": {"$lte": max_time}})
    if user_budget is not None:
        conditions.append({"budget": {"$lte": user_budget}})

    where = None
    if len(conditions) == 1:
        where = conditions[0]
    elif len(conditions) > 1:
        where = {"$and": conditions}

    return collection.query(query_texts=[user_query], n_results=top_n, where=where)


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
    top = scored_recipes[:top_k]
    block = "Here are the best matching recipes based on your available ingredients:\n\n"
    for i, r in enumerate(top, 1):
        meta = r["metadata"]
        ings = r.get("recipe_ingredients") or parse_recipe_ingredients(meta.get("ingredients", ""))
        block += f"Recipe {i}: {meta.get('title', 'Untitled')}\n"
        block += f"Cooking Time: {meta.get('cooking_time')} mins\n"
        block += f"Ingredients: {', '.join(ings)}\n"
        block += f"Directions: {r['document']}\n\n"
    return block


