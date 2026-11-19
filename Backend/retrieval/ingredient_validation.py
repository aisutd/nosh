import ast
import csv
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

from retrieval.ingredients import ALIASES, normalize_name, required_ingredients
from staples import STAPLES


@lru_cache(maxsize=1)
def ingredient_vocabulary():
    path = (
        Path(__file__).resolve().parent.parent
        / "data" / "processed" / "cleaned_recipes.csv"
    )

    names = {
        normalize_name(name)
        for name in [*STAPLES, *ALIASES.keys(), *ALIASES.values()]
    }

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if "ingredients" not in (reader.fieldnames or []):
            raise ValueError("Recipe data has no ingredients column.")

        for row in reader:
            raw = row.get("ingredients") or ""
            lines = [raw]

            # Also support ingredients stored as a Python-style list.
            if raw.strip().startswith("["):
                try:
                    parsed = ast.literal_eval(raw)
                    if isinstance(parsed, list):
                        lines = [line for line in parsed if isinstance(line, str)]
                except (ValueError, SyntaxError):
                    pass

            for line in lines:
                names.update(required_ingredients(line) or set())

    return frozenset(name for name in names if name)


def validate_ingredient(value):
    name = normalize_name(value)

    if not name:
        raise ValueError("Enter an ingredient name.")

    vocabulary = ingredient_vocabulary()

    if name not in vocabulary:
        suggestions = get_close_matches(
            name, sorted(vocabulary), n=1, cutoff=0.8
        )
        message = "Ingredient not recognized. Check the spelling."
        if suggestions:
            message += f" Did you mean {suggestions[0]}?"
        raise ValueError(message)

    return name