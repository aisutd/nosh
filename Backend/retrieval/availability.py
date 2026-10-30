"""Ingredient presence and catalog coverage, calculated without an LLM."""
import math
import os

from retrieval.ingredients import PANTRY, required_ingredients
from retrieval.substitutions import plan_substitutions


def recommendation_threshold():
    """Configurable fraction; generation still requires complete coverage."""
    value = float(os.environ.get("NOSH_MIN_RECIPE_COVERAGE", "0.9"))
    validate_threshold(value)
    return value


def validate_threshold(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 1:
        raise ValueError("Minimum recipe coverage must be greater than 0 and at most 1")


def assess_availability(raw, available, *, context=""):
    required = required_ingredients(raw)
    if required is None:
        return None
    staples = required & PANTRY
    required = required - PANTRY
    present = required & available
    missing = required - available
    substitutions, unresolved = [], []
    for ingredient in sorted(missing):
        plan = plan_substitutions(ingredient, available, context=context)
        if plan:
            substitutions.extend(plan)
        else:
            unresolved.append(ingredient)
    count = len(required)
    return {
        "required_ingredients": sorted(required),
        "available_ingredients": sorted(present),
        "missing_ingredients": sorted(missing),
        "unresolved_ingredients": unresolved,
        "assumed_staples": sorted(staples),
        "substitutions": substitutions,
        "pantry_match": len(present) / count if count else 1.0,
        "coverage": (count - len(unresolved)) / count if count else 1.0,
        "ready_to_cook": not unresolved,
    }


def availability_rank(profile):
    # Stable sorting preserves search relevance among equally covered recipes.
    return (-profile["coverage"], -profile["pantry_match"])


def recipe_availability_rank(recipe, available):
    profile = assess_availability(recipe["metadata"].get("ingredients"), available,
                                  context=recipe.get("document") or "")
    return availability_rank(profile) if profile else (1, 1)
