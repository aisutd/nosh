"""Conservative ingredient-presence matching; not quantities or dietary safety."""
import re
import unicodedata

PANTRY = {"water", "salt", "black pepper", "pepper", "ice"}

ALIASES = {
    "boiling water": "water",
    "half-and-half": "half and half", "half-and-half cream": "half and half",
    "mustard powder": "dry mustard", "ground mustard": "dry mustard",
    # Temperature does not change the pantry requirement for water.
    "cold water": "water", "warm water": "water", "hot water": "water",
    # Plurals
    "tomatoes": "tomato", "potatoes": "potato", "leaves": "leaf",
    # Sugar variations
    "white sugar": "sugar", "granulated sugar": "sugar",
    # Different sugar types are not interchangeable inventory items.
    "light brown sugar": "brown sugar", "dark brown sugar": "brown sugar",
    "confectioners sugar": "powdered sugar", "confectioners' sugar": "powdered sugar",
    "confectioner's sugar": "powdered sugar", "confectioners’ sugar": "powdered sugar",
    "confectioner’s sugar": "powdered sugar", "icing sugar": "powdered sugar",
    "caster sugar": "sugar",
    # Salt and pepper
    "ground black pepper": "black pepper", "ground pepper": "pepper",
    "sea salt": "salt", "table salt": "salt", "kosher salt": "salt",
    "coarse salt": "salt",
    # Flour
    "all-purpose flour": "flour", "plain flour": "flour",
    "all purpose flour": "flour",
    # Dairy
    "whole milk": "milk", "skim milk": "milk",
    "double cream": "heavy cream", "whipping cream": "heavy cream",
    # International synonyms (Week 4: ingredient synonym mapping)
    "capsicum": "bell pepper", "sweet pepper": "bell pepper",
    "courgette": "zucchini",
    "aubergine": "eggplant",
    "coriander": "cilantro",
    "rocket": "arugula",
    "spring onion": "green onion", "scallion": "green onion",
    "bicarbonate of soda": "baking soda", "bicarb": "baking soda",
    "corn starch": "cornstarch", "corn flour": "cornstarch",
    "vanilla extract": "vanilla", "vanilla essence": "vanilla",
    # Ground spices
    "ground cinnamon": "cinnamon", "ground cumin": "cumin",
    "ground ginger": "ginger", "ground turmeric": "turmeric",
    "ground nutmeg": "nutmeg", "ground cloves": "clove",
    # Juice as ingredient name
    "lemon juice": "lemon", "fresh lemon juice": "lemon",
    "lime juice": "lime", "fresh lime juice": "lime",
    "orange juice": "orange",
    # Protein cuts → base protein
    "salmon fillet": "salmon", "salmon filet": "salmon",
    "chicken breast": "chicken", "chicken thigh": "chicken",
    "chicken drumstick": "chicken", "chicken wing": "chicken",
    "pork chop": "pork", "pork loin": "pork",
    "beef steak": "beef", "beef loin": "beef",
    "shrimp": "shrimp", "prawn": "shrimp",
    # Tomato varieties → tomato
    "roma tomato": "tomato", "cherry tomato": "tomato",
    "grape tomato": "tomato", "plum tomato": "tomato",
    # Pomegranate seeds → pomegranate
    "pomegranate seed": "pomegranate",
    # Ice → pantry item
    "ice cube": "ice", "ice water": "water",
}

UNITS = r"(?:cups?|tablespoons?|teaspoons?|tbsp|tsp|pounds?|ounces?|lbs?|oz|grams?|kilograms?|ml|liters?|cloves?|slices?|pinch|pinches|cans?|packages?|sheets?|stalks?|sprigs?|heads?|bunches?|pieces?|filets?|fillets?)"
PREP = r"(?:hulled|chopped|diced|minced|sliced|peeled|quartered|cored|seeded|pitted|crushed|grated|shredded|melted|softened|beaten|divided|rinsed|drained|thawed|sifted|juiced|torn|halved|trimmed|blanched|toasted|roasted|mashed|packed|squeezed|zested|cubed|crumbled|julienned|deveined|deboned|broken|separated|cooled|steamed|boiled|fried|baked|grilled|smoked|canned|frozen|dried|ground)"

# Words that are never food ingredients on their own; discard fragment if this
# is all that remains after prep/unit stripping.
_NON_FOOD = frozenset({
    "thinly", "freshly", "coarsely", "firmly", "evenly", "gently",
    "well", "thoroughly", "loosely", "tightly", "optional", "garnish",
    "bone", "bones", "skin", "fat", "shell", "membrane",
    "removed", "needed", "serving", "more", "chunk", "chunks",
    "piece", "pieces", "portion", "portions",
})


def normalize_name(value):
    value = unicodedata.normalize('NFKC', value.lower()).replace('⁄', '/')
    value = re.sub(r'\([^()]*\)', '', value)
    value = re.sub(r'^[\s\d./–-]+', '', value)
    value = re.sub(rf'^(?:{UNITS}\s+)+', '', value)
    value = re.sub(r'\s+(?:to taste|as needed)$', '', value)
    value = re.sub(rf'\b(?:{PREP}|fresh|ripe|overripe|dried|frozen|organic|raw|whole|boneless|skinless|'
                   r'unsalted|salted|sweetened|unsweetened|large|medium|small|extra|'
                   r'finely|roughly|lightly|thinly|freshly|coarsely|firmly|evenly|into)\b', '', value)
    # Strip trailing purpose phrases: "for garnish", "for decoration", "for serving", etc.
    value = re.sub(r'\s+for\s+\w+$', '', value)
    value = ' '.join(value.split()).strip(' .–—-')
    if value in ALIASES:
        return ALIASES[value]
    words = value.split()
    if words:
        last = words[-1]
        words[-1] = ALIASES.get(last, last[:-3] + 'y' if last.endswith('ies') else
                               last[:-1] if last.endswith('s') and not last.endswith(('ss', 'us')) else last)
    result = ' '.join(words)
    # Second alias pass after singularization (e.g. "salmon fillets" -> "salmon fillet" -> "salmon")
    return ALIASES.get(result, result)


def normalize_available(values, semantic: bool = True):
    """Normalize a list (or comma-string) of user-supplied ingredient names.

    With semantic=True (default) any name not resolved by ALIASES is passed
    through the embedding-based SemanticIngredientMatcher, which maps
    synonyms like 'capsicum' → 'bell pepper' automatically using the
    all-MiniLM-L6-v2 model already loaded by the pipeline.
    """
    if isinstance(values, str):
        values = values.split(',')
    if not isinstance(values, (list, tuple)) or not all(isinstance(v, str) for v in values):
        raise ValueError('available_ingredients must be a list of strings or comma-separated string')

    if semantic:
        from retrieval.semantic_ingredients import get_matcher
        matcher = get_matcher()
    else:
        matcher = None

    names: set[str] = set()
    for value in values:
        name = normalize_name(value)
        if not name:
            continue
        if matcher is not None:
            name = matcher.match(name)
        names.add(name)

    return names | PANTRY


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
        # Discard pure preparation/descriptor fragments (e.g. "thinly sliced",
        # "bones and skin removed") that appear after a comma in ingredient strings.
        tail = re.sub(
            rf'\b(?:{PREP}|and|or|for|finely|roughly|lightly|thinly|freshly|coarsely|'
            r'firmly|evenly|gently|well|thoroughly|optional|more|removed|reserved|'
            r'garnish|garnishing|decoration|decorating|serving|topping|'
            r'bones?|skin|fat|shell|membrane)\b',
            '', fragment.lower(),
        )
        if not tail.strip() or re.fullmatch(r'(?:or )?(?:more )?(?:as needed|to taste)', fragment.lower()):
            continue
        name = normalize_name(fragment)
        if not name:
            return None
        # Discard if every word in the normalized name is a known non-food word
        if all(w in _NON_FOOD for w in name.split()):
            continue
        # A conventional paired seasoning is two requirements, not one name.
        # Do not split arbitrary combinations such as "macaroni and cheese".
        if name == "salt and pepper":
            names.update({"salt", "pepper"})
        elif name == "salt and black pepper":
            names.update({"salt", "black pepper"})
        else:
            names.add(name)
    return names or None


def matches_available(raw, available, *, context="", min_coverage=1.0):
    from retrieval.availability import assess_availability, validate_threshold
    validate_threshold(min_coverage)
    if min_coverage == 1.0:
        from retrieval.substitutions import plan_substitutions
        return plan_substitutions(raw, available, context=context) is not None
    profile = assess_availability(raw, available, context=context)
    return profile is not None and profile["coverage"] >= min_coverage
