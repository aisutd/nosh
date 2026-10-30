"""Source-backed one-hop substitutions from a versioned local data catalog."""
import json
import re
from fractions import Fraction
from pathlib import Path
from retrieval.ingredients import required_ingredients, normalize_name

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data/substitutions.json"


def load_catalog(path=CATALOG_PATH):
    data = json.loads(Path(path).read_text())
    if data.get("version") != 1 or not isinstance(data.get("entries"), list):
        raise ValueError("Unsupported substitution catalog")
    catalog, ids = {}, set()
    for entry in data["entries"]:
        if entry["id"] in ids or normalize_name(entry["ingredient"]) != entry["ingredient"]:
            raise ValueError("Duplicate id or noncanonical substitution ingredient")
        ids.add(entry["id"])
        for measure in [entry["source_amount"], *entry["components"]]:
            if sum(Fraction(part) for part in measure["quantity"].split()) <= 0 or not measure["unit"]:
                raise ValueError("Invalid substitution measurement")
        if not entry["components"] or any(normalize_name(c["ingredient"]) != c["ingredient"] for c in entry["components"]):
            raise ValueError("Invalid replacement components")
        for field in ("instructions", "limitations", "source_url"):
            if not entry.get(field):
                raise ValueError("Missing substitution provenance or guidance")
        for field in ("requires_context", "excludes_context"):
            re.compile(entry[field])
        catalog.setdefault(entry["ingredient"], []).append(entry)
    return catalog


CATALOG = load_catalog()


def plan_substitutions(raw, available, *, context=""):
    """Return a complete plan, [] for an exact match, or None if unsupported.

    Require all components in the normalized pantry. Context-restricted entries
    require source recipe text; the judge still checks culinary suitability.
    Never chain substitutions or infer ingredient quantities in stock.
    """
    required = required_ingredients(raw)
    if required is None:
        return None
    plan = []
    for missing in sorted(required - available):
        def usable(option):
            components = {c["ingredient"] for c in option["components"]}
            return (components <= available
                    and (not option["requires_context"] or re.search(option["requires_context"], context, re.I))
                    and (not option["excludes_context"] or not re.search(option["excludes_context"], context, re.I)))
        option = next((o for o in CATALOG.get(missing, []) if usable(o)), None)
        if option is None:
            return None
        plan.append({"ingredient": missing,
                     "replacement_ingredients": [c["ingredient"] for c in option["components"]],
                     "instructions": option["instructions"], "limitations": option["limitations"],
                     "source_url": option["source_url"], "catalog_id": option["id"],
                     "source_amount": option["source_amount"], "components": option["components"]})
    return plan
