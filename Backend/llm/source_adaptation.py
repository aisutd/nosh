"""Preserve source facts for substitutions whose catalog amounts match exactly.

This is a candidate builder, not an approval bypass. The existing checks and
LLM judge must still accept its recipe suitability and user constraints.
"""
import re
from fractions import Fraction
from retrieval.ingredients import normalize_name
from llm.nosh_generation import ascii_fractions

_VOLUME = {"cup": 48, "cups": 48, "tablespoon": 3, "tablespoons": 3,
           "tbsp": 3, "teaspoon": 1, "teaspoons": 1, "tsp": 1}


def build_source_adaptation(recipe, substitutions):
    """Return a source-preserving draft, or None for unsupported/ambiguous amounts.

    Only exact catalog-batch equivalents are supported initially: no guessed
    scaling, mass conversions, partial ingredient omissions, or recursive swaps.
    """
    if not substitutions:
        return None
    metadata = recipe.get("metadata", {})
    raw = metadata.get("ingredients", "")
    directions = metadata.get("directions", "")
    title = recipe.get("title") or metadata.get("recipe_name")
    if not raw or not directions or not title:
        return None
    fragments = re.split(r",(?![^()]*\))", raw)
    changes, preparations = [], []
    adapted_directions = directions
    removed = set()
    for swap in substitutions:
        name = swap["ingredient"]
        indices = [i for i, fragment in enumerate(fragments) if normalize_name(fragment.strip()) == name]
        if len(indices) != 1:
            return None
        index = indices[0]
        match = re.match(r"^\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s+(cups?|tablespoons?|teaspoons?|tbsp|tsp)\b", ascii_fractions(fragments[index]), re.I)
        base = swap.get("source_amount", {})
        if not match or base.get("unit") not in _VOLUME:
            return None
        try:
            actual = sum(Fraction(n) for n in match[1].split()) * _VOLUME[match[2].lower()]
            expected = sum(Fraction(n) for n in base["quantity"].split()) * _VOLUME[base["unit"]]
        except (ValueError, ZeroDivisionError, KeyError):
            return None
        if actual != expected:
            return None
        components = " and ".join(swap["replacement_ingredients"])
        # Keep the original prose/amounts for every unaffected ingredient and step.
        pattern = rf"\b{re.escape(name)}\b"
        if not re.search(pattern, adapted_directions, re.I):
            return None
        replacement = "prepared " + components + " mixture"
        adapted_directions = re.sub(pattern, replacement, adapted_directions, flags=re.I)
        preparations.append(re.sub(pattern, "the replacement", swap["instructions"], flags=re.I))
        changes.append(f"- {name} replaced with {components}. {swap['instructions']} {swap['limitations']}")
        removed.add(index)
    remaining = ",".join(fragment for i, fragment in enumerate(fragments) if i not in removed).strip()
    steps = ["Measure the remaining source ingredients: " + remaining + ".", *preparations]
    steps.extend(line.strip() for line in adapted_directions.splitlines() if line.strip())
    return (f"Recipe Name: {title}\nChanges:\n" + "\n".join(changes)
            + "\nSteps:\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1)))
