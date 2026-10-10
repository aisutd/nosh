"""Conservative ingredient-presence matching; not quantities or dietary safety."""
import re
import unicodedata

PANTRY = {"water", "salt", "black pepper", "pepper"}
ALIASES = {"tomatoes": "tomato", "potatoes": "potato", "leaves": "leaf",
           "white sugar": "sugar", "granulated sugar": "sugar",
           "ground black pepper": "black pepper", "ground pepper": "pepper",
           "sea salt": "salt", "table salt": "salt", "kosher salt": "salt"}
UNITS = r"(?:cups?|tablespoons?|teaspoons?|tbsp|tsp|pounds?|ounces?|lbs?|oz|grams?|kilograms?|ml|liters?|cloves?|slices?|pinch|pinches|cans?|packages?|sheets?|stalks?|sprigs?)"
PREP = r"(?:chopped|diced|minced|sliced|peeled|quartered|cored|seeded|pitted|crushed|grated|shredded|melted|softened|beaten|divided|rinsed|drained|thawed|sifted|juiced)"


def normalize_name(value):
    value = unicodedata.normalize('NFKC', value.lower()).replace('⁄', '/')
    value = re.sub(r'\([^()]*\)', '', value)
    value = re.sub(r'^[\s\d./–-]+', '', value)
    value = re.sub(rf'^(?:{UNITS}\s+)+', '', value)
    value = re.sub(r'\s+(?:to taste|as needed)$', '', value)
    value = re.sub(rf'\b(?:{PREP}|fresh|ripe|large|medium|small|finely|roughly|lightly)\b', '', value)
    value = ' '.join(value.split()).strip(' .')
    if value in ALIASES:
        return ALIASES[value]
    words = value.split()
    if words:
        last = words[-1]
        words[-1] = ALIASES.get(last, last[:-3] + 'y' if last.endswith('ies') else
                               last[:-1] if last.endswith('s') and not last.endswith(('ss', 'us')) else last)
    return ' '.join(words)


def normalize_available(values):
    if isinstance(values, str):
        values = values.split(',')
    if not isinstance(values, (list, tuple)) or not all(isinstance(v, str) for v in values):
        raise ValueError('available_ingredients must be a list of strings or comma-separated string')
    return {name for value in values if (name := normalize_name(value))} | PANTRY


def required_ingredients(raw):
    """Keep unrecognized fragments as requirements (conservative false negatives).

    Commas inside parentheses are not separators. Known preparation-only tails
    attach to the preceding ingredient. Optional ingredients are still required:
    their omission must not silently leave instructions using unavailable food.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    raw = re.sub(r'\([^()]*\)', lambda m: m[0].replace(',', ' '), raw)
    names = set()
    for fragment in raw.split(','):
        fragment = fragment.strip()
        if not fragment:
            continue
        # Only discard preparation-only fragments, not e.g. "chopped onion".
        tail = re.sub(rf'\b(?:{PREP}|and|or|finely|roughly|lightly)\b', '', fragment.lower())
        if not tail.strip() or re.fullmatch(r'(?:or )?(?:more )?(?:as needed|to taste)', fragment.lower()):
            continue
        name = normalize_name(fragment)
        if not name:
            return None
        names.add(name)
    return names or None


def matches_available(raw, available):
    required = required_ingredients(raw)
    return required is not None and required <= available
