"""Preserve source facts for substitutions using exact catalog ratios.

This is a candidate builder, not an approval bypass. The existing checks and
LLM judge must still accept its recipe suitability and user constraints.
"""
import re
from fractions import Fraction
from retrieval.ingredients import normalize_name
from llm.nosh_generation import ascii_fractions

_VOLUME = {"cup": 48, "cups": 48, "tablespoon": 3, "tablespoons": 3,
           "tbsp": 3, "teaspoon": 1, "teaspoons": 1, "tsp": 1}


def component_line(component):
    unit, _, preparation = component["unit"].partition(" ")
    return f"{component['quantity']} {unit} {component['ingredient']} {preparation}".strip()


def scaled_components(swap, factor):
    output = []
    for component in swap["components"]:
        try:
            amount = sum(Fraction(n) for n in component["quantity"].split()) * factor
        except (ValueError, ZeroDivisionError):
            return None
        if amount <= 0:
            return None
        unit, _, suffix = component["unit"].partition(" ")
        # Small cup fractions are easier to measure in spoons.
        if unit == "cup" and amount < 1:
            amount *= 48
            unit = "teaspoon"
            if amount >= 3:
                amount /= 3
                unit = "tablespoon"
        whole, numerator = divmod(amount.numerator, amount.denominator)
        quantity = (f"{whole} {numerator}/{amount.denominator}" if whole and numerator
                    else str(whole) if not numerator else f"{numerator}/{amount.denominator}")
        output.append({**component, "quantity": quantity,
                       "unit": unit + (" " + suffix if suffix else "")})
    return output


def resolve_substitution_amounts(context, substitutions):
    """Annotate catalog plans with recipe-specific volume arithmetic for the LLM."""
    source = re.search(r"^Ingredients: (.+)$", context, re.M)
    resolved = []
    for swap in substitutions or []:
        item = dict(swap)
        fragments = re.split(r",(?![^()]*\))", source[1]) if source else []
        matches = [line for line in fragments if normalize_name(line.strip()) == swap["ingredient"]]
        if len(matches) == 1:
            match = re.match(r"^\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s+(cups?|tablespoons?|teaspoons?|tbsp|tsp)\b", ascii_fractions(matches[0]), re.I)
            base = swap.get("source_amount", {})
            if match and base.get("unit") in _VOLUME:
                try:
                    actual = sum(Fraction(n) for n in match[1].split()) * _VOLUME[match[2].lower()]
                    expected = sum(Fraction(n) for n in base["quantity"].split()) * _VOLUME[base["unit"]]
                    if actual > 0 and expected > 0:
                        components = scaled_components(swap, actual / expected)
                        if components:
                            item.update(recipe_source_amount={"quantity": match[1], "unit": match[2]},
                                        scale_factor=str(actual / expected), recipe_components=components)
                            # For templated plans, send one consistent set of amounts.
                            # Keep the reference batch in the catalog, not in competing
                            # instructions that a small judge can mistake for this recipe.
                            template = swap.get("preparation_template")
                            if template:
                                item.update(source_amount=item["recipe_source_amount"], components=components,
                                            instructions=template.format(**{
                                                f"component_{i}": component_line(c)
                                                for i, c in enumerate(components)}))
                except (ValueError, ZeroDivisionError, KeyError):
                    pass
        resolved.append(item)
    return resolved


def build_source_adaptation(recipe, substitutions):
    """Return a source-preserving draft, or None for unsupported/ambiguous amounts.

    Scale volume ratios only when the catalog supplies a preparation template.
    Ambiguous amounts, divided usage and unsupported conversions fall back.
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
        if actual <= 0 or expected <= 0:
            return None
        factor = actual / expected
        template = swap.get("preparation_template")
        if factor != 1 and not template:
            return None
        # Do not guess how to distribute a replacement over partial uses.
        if re.search(r"\b(divided|remaining|reserved)\b", fragments[index], re.I):
            return None
        scaled = scaled_components(swap, factor)
        if scaled is None:
            return None
        preparation = (template.format(**{f"component_{i}": component_line(c)
                                         for i, c in enumerate(scaled)})
                       if template else swap["instructions"])
        components = " and ".join(swap["replacement_ingredients"])
        # Keep the original prose/amounts for every unaffected ingredient and step.
        pattern = rf"\b{re.escape(name)}\b"
        if not re.search(pattern, adapted_directions, re.I):
            return None
        # A measured use in the directions may be only part of the total.
        # Leave that adaptation to the model rather than retain a wrong volume.
        if re.search(r"\b(?:cups?|tablespoons?|teaspoons?|tbsp|tsp)\s+(?:of\s+)?" + pattern,
                     adapted_directions, re.I):
            return None
        replacement = "prepared " + components + " mixture"
        adapted_directions = re.sub(pattern, replacement, adapted_directions, flags=re.I)
        preparations.append(re.sub(pattern, "the replacement", preparation, flags=re.I))
        changes.append(f"- {name} replaced with {components}. {preparation} {swap['limitations']}")
        removed.add(index)
    remaining = ",".join(fragment for i, fragment in enumerate(fragments) if i not in removed).strip()
    steps = ["Measure the remaining source ingredients: " + remaining + ".", *preparations]
    steps.extend(line.strip() for line in adapted_directions.splitlines() if line.strip())
    return (f"Recipe Name: {title}\nChanges:\n" + "\n".join(changes)
            + "\nSteps:\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1)))


def build_inventory_ingredients(recipe, substitutions):
    """Return source lines with calculated replacements, or None if ambiguous.

    Reuse the source adapter's quantity checks; do not infer consumption amounts
    from model prose. Inventory's existing unit conversion remains authoritative.
    """
    raw = recipe.get("metadata", {}).get("ingredients", "")
    if not raw:
        return None
    lines = [s.strip() for s in re.split(r",(?![^()]*\))", raw) if s.strip()]
    if not substitutions:
        return lines
    if build_source_adaptation(recipe, substitutions) is None:
        return None
    replacements = {swap["ingredient"]: swap for swap in substitutions}
    output = []
    for line in lines:
        swap = replacements.get(normalize_name(line))
        if swap is None:
            output.append(line)
            continue
        match = re.match(r"^\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s+(cups?|tablespoons?|teaspoons?|tbsp|tsp)\b", ascii_fractions(line), re.I)
        actual = sum(Fraction(n) for n in match[1].split()) * _VOLUME[match[2].lower()]
        base = swap["source_amount"]
        expected = sum(Fraction(n) for n in base["quantity"].split()) * _VOLUME[base["unit"]]
        for component in scaled_components(swap, actual / expected):
            output.append(component_line(component))
    return output
