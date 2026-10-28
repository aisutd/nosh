"""Check request scope, retrieve a recipe, generate once, and judge the answer."""
from retrieval.nosh_retrieval import (
    normalize_ingredients,
    format_recipes_for_llm,
)
from retrieval.hybrid_search import hybrid_search_recipes as search_recipes
from llm.nosh_generation import (
    generate_recipe,
    evaluate_generation,
    judge_passed,
    classify_request,
    OUT_OF_SCOPE,
    INSUFFICIENT_CONTEXT,
    UNSUPPORTED_PREFERENCES,
)


def run_nosh(detected_ings, *, user_query="", top_k=5, max_time=None, collection=None, retrieve_only=False, selected_recipe_id=None):
    """Return only judge-approved generation; refusals use message, not recipe.

    Ingredient labels or comma-separated ingredients are accepted. Free-form
    requests go in user_query. Model-based scope and judgment are fallible.
    """
    if not isinstance(user_query, str):
        raise ValueError("user_query must be a string")
    if not isinstance(detected_ings, (str, list, tuple)) or (
        not isinstance(detected_ings, str) and not all(isinstance(i, str) for i in detected_ings)
    ):
        raise ValueError("detected_ings must be ingredient strings")
    ingredients = normalize_ingredients(detected_ings)
    if not ingredients and not user_query.strip():
        return {"status": "no_ingredients", "recipe": None, "recipes": [],
                "message": "Please provide your available ingredients."}

    # Classify before Chroma: an unrelated question must not retrieve random recipes.
    scope = classify_request(ingredients, user_query)
    if scope["status"] != "in_scope":
        message = {
            "out_of_scope": OUT_OF_SCOPE,
            "unsupported_preferences": UNSUPPORTED_PREFERENCES,
            "insufficient_input": "Please provide ingredients and a clear cooking request.",
            "guardrail_error": "Could not validate request scope. Please try again.",
        }[scope["status"]]
        return {"status": scope["status"], "message": message, "recipe": None, "recipes": []}
    if not ingredients:
        return {"status": "no_ingredients", "recipe": None, "recipes": [],
                "message": "Please provide your available ingredients."}

    available = ", ".join(ingredients)
    search_query = f"{user_query.strip()} Ingredients: {available}" if user_query.strip() else available
    if selected_recipe_id is not None:
        from retrieval.nosh_retrieval import get_collection
        from retrieval.ingredients import normalize_available, matches_available
        collection = collection if collection is not None else get_collection()
        source = collection.get(ids=[selected_recipe_id], include=["documents", "metadatas"])
        if not source["ids"]:
            return {"status": "recipe_not_found", "recipe": None, "recipes": [],
                    "message": "This recipe is no longer available. Search again."}
        metadata = source["metadatas"][0] or {}
        if not matches_available(metadata.get("ingredients", ""), normalize_available(detected_ings, semantic=False), context=source["documents"][0] or ""):
            return {"status": "ingredients_changed", "recipe": None, "recipes": [],
                    "message": "Your pantry no longer covers this recipe. Search again."}
        recipes = [{"id": source["ids"][0], "title": metadata.get("recipe_name", "Untitled"),
                    "url": metadata.get("url", ""), "document": source["documents"][0],
                    "metadata": metadata, "ingredients": metadata.get("ingredients", ""),
                    "directions": metadata.get("directions", ""), "similarity": None}]
    else:
        recipes = search_recipes(
            search_query, top_k=top_k, max_time=max_time, collection=collection,
            available_ingredients=detected_ings,
        )
    if not recipes:
        return {"status": "no_recipes_found", "recipe": None, "recipes": [],
                "message": "No matching recipes were found for those constraints."}

    from retrieval.ingredients import normalize_available
    from retrieval.substitutions import plan_substitutions
    inventory = normalize_available(detected_ings, semantic=False)
    for recipe in recipes:
        recipe["substitutions"] = plan_substitutions(recipe["metadata"].get("ingredients", ""), inventory, context=recipe["document"] or "")
    recipes = [recipe for recipe in recipes if recipe["substitutions"] is not None]
    if not recipes:
        return {"status": "no_recipes_found", "recipe": None, "recipes": [],
                "message": "No recipes can be made with your available ingredients and supported substitutions."}
    # Keep relevance ordering within each group; favor fewer adaptations.
    recipes.sort(key=lambda recipe: len(recipe["substitutions"]))
    substitutions = recipes[0]["substitutions"]

    if retrieve_only:
        return {"status": "ok", "message": "Choose a recipe to cook.", "recipe": None, "recipes": recipes}

    # Adapt one source recipe so the response has a clear, traceable source.
    context = format_recipes_for_llm(recipes, top_k=1)
    from llm.source_adaptation import build_source_adaptation
    answer = build_source_adaptation(recipes[0], substitutions)
    if answer is None:
        answer = generate_recipe(available_ingredients=available, retrieved_context=context,
                                 user_query=user_query, max_time=max_time, substitutions=substitutions)
    if answer in (INSUFFICIENT_CONTEXT, OUT_OF_SCOPE):
        return {"status": "insufficient_context" if answer == INSUFFICIENT_CONTEXT else "out_of_scope",
                "message": answer, "recipe": None, "recipes": recipes}
    verdict = evaluate_generation(available, context, answer,
                                  user_query=user_query, max_time=max_time, substitutions=substitutions)
    passed = judge_passed(verdict)
    if not passed:
        # One bounded correction attempt; failed drafts are never cooking instructions.
        corrected = generate_recipe(
            available_ingredients=available, retrieved_context=context,
            user_query=user_query, max_time=max_time, substitutions=substitutions,
            repair_feedback={"previous_output": answer, "validation": verdict},
        )
        if corrected not in (INSUFFICIENT_CONTEXT, OUT_OF_SCOPE):
            verdict = evaluate_generation(available, context, corrected,
                                          user_query=user_query, max_time=max_time,
                                          substitutions=substitutions)
            passed = judge_passed(verdict)
            if passed:
                answer = corrected

    return {
        "status": "ok" if passed else "failed_validation",
        "message": "Recipe validated." if passed else "The adapted instructions could not be verified. You can review the source ingredients and suggested substitutions below, or try generating again.",
        "recipe": answer if passed else None,
        "source_recipe": recipes[0]["title"],
        "source_url": recipes[0]["url"],
        "similarity": recipes[0]["similarity"],
        "judge_verdict": verdict,
        "substitutions": substitutions if passed else [],
        "recipes": recipes,
    }


def main():
    import argparse
    import json
    import sys
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ingredients", help='Comma-separated ingredients, e.g. "salmon, lemon, garlic"')
    parser.add_argument("--chat", action="store_true", help="Ask follow-up questions about the approved recipe")
    parser.add_argument("--show-drafts", action="store_true", help="Show chat drafts and judge diagnostics; requires --chat")
    parser.add_argument("--debug", action="store_true", help="Show retrieved titles and judge verdict on stderr")
    parser.add_argument("--query", default="", help="Optional cooking request")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-time", type=float, help="Maximum total recipe time in minutes")
    args = parser.parse_args()
    if args.show_drafts and not args.chat:
        parser.error("--show-drafts requires --chat")
    session = None
    if args.chat:
        from cooking_session import CookingSession
        session = CookingSession()
    runner = session.start if session else run_nosh
    result = runner(args.ingredients, user_query=args.query, top_k=args.top_k, max_time=args.max_time)
    if args.debug:
        diagnostics = {
            "status": result["status"],
            "source_recipe": result.get("source_recipe"),
            "judge_verdict": result.get("judge_verdict"),
            "retrieved_recipes": [
                {"title": recipe["title"], "similarity": recipe["similarity"]}
                for recipe in result["recipes"]
            ],
        }
        print(json.dumps(diagnostics, indent=2), file=sys.stderr)
    if result["status"] == "ok":
        print(f"Source: {result['source_recipe']} ({result['source_url']})\n")
        print(result["recipe"])
        if session:
            from cooking_session import chat_loop
            chat_loop(session, show_drafts=args.show_drafts)
    else:
        print(result["message"])


if __name__ == "__main__":
    main()
