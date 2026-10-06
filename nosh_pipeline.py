"""Retrieve recipes, generate instructions, and validate the LLM output."""

from nosh_retrieval import (
    get_collection,
    normalize_ingredients,
    retrieve_candidate_recipes,
    rank_by_ingredient_overlap,
    format_recipes_for_llm,
)

from nosh_generation import generate_recipe, check_output, evaluate_generation, judge_passed

# Skip recipes where less than this fraction of the recipe's ingredients are in the fridge
MIN_OVERLAP = 0.5


def run_nosh(detected_ings, dietary=None, max_time=None, budget=None,
             max_attempts=3, collection=None):
    """
    detected_ings: list of labels from YOLOv8, e.g. ["Chicken", "onions", "water"]
    Returns a dict with the recipe, verdicts, and which recipe was used.
    """
    if collection is None:
        collection = get_collection()

    ings = normalize_ingredients(detected_ings)
    if not ings:
        return {"status": "no_ingredients", "recipe": None}
    ing_str = ", ".join(ings)

    # Retrieve, relaxing filters step by step if nothing matches
    attempts_filters = [
        (dietary, max_time, budget),
        (dietary, max_time, None),   # drop budget
        (dietary, None, None),       # drop time
    ]
    results = None
    for d, t, b in attempts_filters:
        r = retrieve_candidate_recipes(" ".join(ings), d, t, b, collection=collection)
        if r["ids"] and r["ids"][0]:
            results = r
            break
    if results is None:
        return {"status": "no_recipes_found", "recipe": None}

    ranked = rank_by_ingredient_overlap(results, ings)

    # Drop weak matches so the LLM never gets a recipe it can't realistically make
    good = [r for r in ranked if r["overlap_score"] >= MIN_OVERLAP]
    if not good:
        return {
            "status": "no_good_match",
            "recipe": None,
            "closest": [(r["metadata"].get("title"), round(r["overlap_score"], 2)) for r in ranked[:3]],
        }

    # Try the best recipes in order; first one that passes both checks wins
    attempts = []
    for candidate in good[:max_attempts]:
        missing = [i for i in candidate["recipe_ingredients"] if i not in set(ings)]
        context = format_recipes_for_llm([candidate], top_k=1)
        output = generate_recipe(ing_str, context, missing_ingredients=missing)
        problems = check_output(output, ings, candidate["recipe_ingredients"])

        verdict = None
        if not problems:  # only spend a judge call if the code check passed
            verdict = evaluate_generation(ing_str, context, output)

        attempt = {
            "status": "ok" if (not problems and judge_passed(verdict)) else "failed_checks",
            "recipe": output,
            "source_recipe": candidate["metadata"].get("title"),
            "overlap": round(candidate["overlap_score"], 2),
            "code_problems": problems,
            "judge_verdict": verdict,
        }
        attempts.append(attempt)
        if attempt["status"] == "ok":
            attempt["attempts_made"] = len(attempts)
            return attempt

    # Nothing passed: return the BEST-ranked attempt (not the last), with a log of all tries
    best = dict(attempts[0])
    best["attempts_made"] = len(attempts)
    best["attempt_log"] = [(a["source_recipe"], a["code_problems"] or a["judge_verdict"]) for a in attempts]
    return best

