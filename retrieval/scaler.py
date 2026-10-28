"""Scales recipe ingredient quantities from the original serving size to a requested one.

Given a raw ingredient string like '2 cups flour' and a scaling ratio, this module
returns '1 cup flour'. The scaled context is injected into the LLM prompt so the
generated recipe already contains the correct amounts for the requested serving size.

Usage:
    from retrieval.scaler import scale_recipe_context
    scaled = scale_recipe_context(context, original_servings=4, requested_servings=2)
"""

import re
import unicodedata

# Maps singular and plural unit names to a canonical singular form
_UNIT_MAP = {
    "cup": "cup", "cups": "cup",
    "tablespoon": "tablespoon", "tablespoons": "tablespoon", "tbsp": "tablespoon",
    "teaspoon": "teaspoon", "teaspoons": "teaspoon", "tsp": "teaspoon",
    "pound": "pound", "pounds": "pound", "lb": "pound", "lbs": "pound",
    "ounce": "ounce", "ounces": "ounce", "oz": "ounce",
    "gram": "gram", "grams": "gram", "g": "gram",
    "kilogram": "kilogram", "kilograms": "kilogram", "kg": "kilogram",
    "liter": "liter", "liters": "liter", "l": "liter",
    "milliliter": "milliliter", "milliliters": "milliliter", "ml": "milliliter",
    "clove": "clove", "cloves": "clove",
    "slice": "slice", "slices": "slice",
    "piece": "piece", "pieces": "piece",
    "inch": "inch", "inches": "inch",
}

# Plural forms for units that don't just add 's'
_PLURAL = {
    "cup": "cups", "tablespoon": "tablespoons", "teaspoon": "teaspoons",
    "pound": "pounds", "ounce": "ounces", "gram": "grams",
    "kilogram": "kilograms", "liter": "liters", "milliliter": "milliliters",
    "clove": "cloves", "slice": "slices", "piece": "pieces", "inch": "inches",
    "lb": "lbs", "tbsp": "tbsp", "tsp": "tsp", "oz": "oz",
}

# Convert small tablespoon amounts down to teaspoons for readability
_TBSP_TO_TSP = 3


def _normalize_unicode(text: str) -> str:
    """Replace unicode fraction characters with ASCII equivalents.

    Replacements are done BEFORE NFKC normalization because NFKC converts
    vulgar fractions like ¼ into "1⁄4" (with a fraction slash U+2044, not
    ASCII /), which our digit-based regex cannot match. Any leftover fraction
    slashes are converted to ASCII / as a fallback.
    """
    replacements = {"½": "1/2", "⅓": "1/3", "¼": "1/4", "¾": "3/4",
                    "⅔": "2/3", "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"}
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    text = unicodedata.normalize("NFKC", text)
    # NFKC may still introduce fraction slashes from other sources — normalise them too
    text = text.replace("\u2044", "/")
    return text


def _parse_quantity(token: str) -> float | None:
    """Parse a quantity token like '2', '1/2', or '1 1/2' into a float."""
    token = token.strip()
    # Mixed number like "1 1/2"
    mixed = re.fullmatch(r"(\d+)\s+(\d+)/(\d+)", token)
    if mixed:
        return int(mixed.group(1)) + int(mixed.group(2)) / int(mixed.group(3))
    # Simple fraction like "1/2"
    frac = re.fullmatch(r"(\d+)/(\d+)", token)
    if frac:
        return int(frac.group(1)) / int(frac.group(2))
    # Plain integer or decimal
    try:
        return float(token)
    except ValueError:
        return None


def _format_quantity(value: float) -> str:
    """Format a float back to a clean readable quantity string."""
    if value <= 0:
        return "0"

    # Supported fractions — pick the CLOSEST one within tolerance, not just the first.
    fractions = [
        (7/8, "7/8"), (4/5, "4/5"), (3/4, "3/4"), (2/3, "2/3"), (3/5, "3/5"),
        (5/8, "5/8"), (1/2, "1/2"), (2/5, "2/5"), (3/8, "3/8"),
        (1/3, "1/3"), (1/4, "1/4"), (1/5, "1/5"), (1/8, "1/8"),
    ]

    whole = int(value)
    remainder = value - whole

    # Find the closest fraction within tolerance 0.04
    best_str, best_diff = None, 0.04
    for frac_val, frac_str in fractions:
        diff = abs(remainder - frac_val)
        if diff < best_diff:
            best_diff, best_str = diff, frac_str
    if best_str:
        return f"{whole} {best_str}".strip() if whole else best_str

    # Round to 2 decimal places, strip trailing zeros
    rounded = round(value, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return str(rounded).rstrip("0").rstrip(".")


def _pluralize(unit: str, value: float) -> str:
    """Return singular or plural unit based on quantity. Values <= 1 use singular."""
    if value <= 1:
        return unit
    return _PLURAL.get(unit, unit + "s")


def _scale_line(line: str, ratio: float) -> str:
    """Scale all quantity+unit pairs found in a single ingredient line."""
    line = _normalize_unicode(line)

    # Match patterns like: "2 1/2 cups", "1/4 cup", "3", "½ tablespoon"
    pattern = re.compile(
        r"(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"   # quantity
        r"(\s+)"                                        # space
        r"(" + "|".join(re.escape(u) for u in sorted(_UNIT_MAP, key=len, reverse=True)) + r")?"  # optional unit
        , re.IGNORECASE
    )

    def replace_match(m):
        """Scale a single quantity match and reformat it."""
        qty_str = m.group(1).strip()
        space = m.group(2)
        unit_str = m.group(3)

        # Handle mixed numbers like "2 1/2" — they appear as two tokens; handle above
        qty = _parse_quantity(qty_str)
        if qty is None:
            return m.group(0)

        scaled = qty * ratio

        # Unit conversions for readability at small scales
        if unit_str:
            canonical = _UNIT_MAP.get(unit_str.lower())
            if canonical == "tablespoon" and scaled < 1:
                # e.g. 0.5 tbsp → 1.5 tsp
                scaled_tsp = scaled * _TBSP_TO_TSP
                formatted = _format_quantity(scaled_tsp)
                return f"{formatted}{space}{_pluralize('teaspoon', scaled_tsp)}"
            if canonical == "cup" and scaled < 0.125:
                # e.g. 0.05 cup → ~2.5 tsp (1 cup = 48 tsp)
                scaled_tsp = scaled * 48
                formatted = _format_quantity(scaled_tsp)
                return f"{formatted}{space}{_pluralize('teaspoon', scaled_tsp)}"
            if canonical:
                formatted = _format_quantity(scaled)
                return f"{formatted}{space}{_pluralize(canonical, scaled)}"

        formatted = _format_quantity(scaled)
        return f"{formatted}{space}" + (unit_str if unit_str else "")

    scaled = pattern.sub(replace_match, line)

    # Add (s) to count nouns (no unit) that are > 1 and sit immediately before a
    # comma or end-of-string.  Lookahead skips adjectives: in "6 ripe bananas,"
    # "ripe" is followed by " bananas," so it won't match; only "bananas" would,
    # but it's already plural.  "2 egg," → "2 egg(s)".
    def _add_count_plural(m):
        qty_str, word = m.group(1), m.group(2)
        qty = _parse_quantity(qty_str.strip())
        if qty and qty > 1 and word.lower() not in _UNIT_MAP:
            return f"{qty_str} {word}(s)"
        return m.group(0)

    scaled = re.sub(
        r"(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s+([a-zA-Z]+)(?=\s*(?:,|$))",
        _add_count_plural, scaled
    )

    return scaled


def scale_ingredients(ingredients_text: str, ratio: float) -> str:
    """Scale all ingredient quantities in a multi-line ingredients block."""
    if ratio == 1.0:
        return ingredients_text
    lines = ingredients_text.splitlines()
    return "\n".join(_scale_line(line, ratio) for line in lines)


def scale_recipe_context(context: str, original_servings: int, requested_servings: int) -> str:
    """Scale the ingredient quantities in a formatted recipe context string.

    Finds the Ingredients section in the LLM context block, scales all quantities
    by the ratio requested_servings / original_servings, and returns the updated
    context ready to pass to the LLM.
    """
    if original_servings <= 0 or requested_servings <= 0:
        return context
    ratio = requested_servings / original_servings
    if ratio == 1.0:
        return context

    # Find and scale only the Ingredients line/section.
    # Actual document format: "Ingredients: a, b, c\nDirections: ..."
    # The colon may be followed by a space (single-line) or a newline (multi-line block).
    ing_match = re.search(r"(Ingredients:[ \t]*)(.*?)(\nDirections:)", context, re.DOTALL | re.IGNORECASE)
    if not ing_match:
        # No clear Ingredients section — scale the whole context as a fallback
        return scale_ingredients(context, ratio)

    scaled_ing = scale_ingredients(ing_match.group(2), ratio)
    return (
        context[:ing_match.start(2)]
        + scaled_ing
        + context[ing_match.end(2):]
    )
