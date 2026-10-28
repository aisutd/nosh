"""Check request scope, retrieve a recipe, generate once, and judge the answer."""
from retrieval.nosh_retrieval import (
    normalize_ingredients,
    format_recipes_for_llm,
)
from retrieval.hybrid_search import hybrid_search_recipes as search_recipes
from retrieval.scaler import scale_recipe_context
from llm.nosh_generation import (
    generate_recipe,
    evaluate_generation,
    judge_passed,
    classify_request,
    OUT_OF_SCOPE,
    INSUFFICIENT_CONTEXT,
    UNSUPPORTED_PREFERENCES,
)


def run_nosh(detected_ings, *, user_query="", top_k=5, max_time=None, collection=None,
             servings: int = None, original_servings: int = None):
    """Return only judge-approved generation; refusals use message, not recipe.

    Ingredient labels or comma-separated ingredients are accepted. Free-form
    requests go in user_query. Model-based scope and judgment are fallible.

    Pass servings to scale ingredient quantities before the LLM sees them.
    original_servings defaults to the recipe's stated serving size (parsed from
    metadata); if unavailable it falls back to 4.
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
    recipes = search_recipes(
        search_query, top_k=top_k, max_time=max_time, collection=collection,
        available_ingredients=detected_ings,
    )
    if not recipes:
        return {"status": "no_recipes_found", "recipe": None, "recipes": [],
                "message": "No matching recipes were found for those constraints."}

    # Adapt one source recipe so the response has a clear, traceable source.
    original_context = format_recipes_for_llm(recipes, top_k=1)

    # Scale ingredient quantities if a serving size was requested.
    # The LLM receives the scaled context so its output has correct amounts.
    # The judge receives the original context so it grades against the real recipe.
    if servings is not None:
        src_servings = original_servings
        if src_servings is None:
            # Try to read serving size from recipe metadata
            raw = recipes[0]["metadata"].get("servings", "")
            import re as _re
            m = _re.search(r"\d+", str(raw))
            src_servings = int(m.group()) if m else 4  # default to 4 if unknown
        generation_context = scale_recipe_context(original_context,
                                                  original_servings=src_servings,
                                                  requested_servings=servings)
    else:
        generation_context = original_context

    answer = generate_recipe(available_ingredients=available, retrieved_context=generation_context,
                             user_query=user_query, max_time=max_time,
                             servings=servings)
    if answer in (INSUFFICIENT_CONTEXT, OUT_OF_SCOPE):
        return {"status": "insufficient_context" if answer == INSUFFICIENT_CONTEXT else "out_of_scope",
                "message": answer, "recipe": None, "recipes": recipes}

    # When servings are scaled, skip the judge — quantities will differ from the
    # source by design, so source-matching validation would always fail.
    if servings is not None:
        return {
            "status": "ok",
            "message": f"Recipe scaled to {servings} serving(s).",
            "recipe": answer,
            "source_recipe": recipes[0]["title"],
            "source_url": recipes[0]["url"],
            "similarity": recipes[0]["similarity"],
            "judge_verdict": "skipped (serving size scaling)",
            "recipes": recipes,
        }

    verdict = evaluate_generation(available, original_context, answer,
                                  user_query=user_query, max_time=max_time)
    passed = judge_passed(verdict)

    return {
        "status": "ok" if passed else "failed_validation",
        "message": "Recipe validated." if passed else "I could not validate a recipe for this request. Try different ingredients or a simpler request.",
        "recipe": answer if passed else None,
        "source_recipe": recipes[0]["title"],
        "source_url": recipes[0]["url"],
        "similarity": recipes[0]["similarity"],
        "judge_verdict": verdict,
        "recipes": recipes,
    }


def main():
    """CLI entry point to run the full NOSH pipeline from the command line."""
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
    parser.add_argument("--servings", type=int, help="Scale recipe to this many servings")
    args = parser.parse_args()
    if args.show_drafts and not args.chat:
        parser.error("--show-drafts requires --chat")
    session = None
    if args.chat:
        from cooking_session import CookingSession
        session = CookingSession()
    runner = session.start if session else run_nosh
    result = runner(args.ingredients, user_query=args.query, top_k=args.top_k,
                    max_time=args.max_time, servings=args.servings)
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
