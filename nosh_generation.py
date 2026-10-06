import re
import ollama

from nosh_retrieval import normalize_ingredient, normalize_ingredients

GEN_MODEL = "llama3.2"
JUDGE_MODEL = "gemma2"

BASE_SYSTEM_RULES = """
You are a cooking assistant. Rewrite a recipe using ONLY the available ingredients, plus water, salt, and pepper.

Rules:
- Do NOT use any ingredient that is not on the available list (oil and butter are NOT allowed unless listed; use a dry pan or a splash of water).
- Compare the original recipe to the available ingredients. Every original ingredient that is not available MUST appear in the Changes section.
- Write '<ingredient> omitted' if nothing suitable is available. Write '<ingredient> replaced with <X>' only if X is on the available list.
- The Steps section must never mention omitted or replaced ingredients.
- Do NOT add available ingredients that are not part of the original recipe, unless you use one to replace a missing ingredient.
- If the message says 'Missing ingredients: none', write '- none' under Changes.
- Output EXACTLY the two sections below and nothing else.

Example
Available ingredients: eggs, cheese, tomato
Original recipe: Omelette: whisk eggs, add mushrooms and spinach, top with cheese.

Changes:
- mushrooms omitted
- spinach replaced with tomato

Recipe Name: Omelette

Steps:
1. Whisk the eggs with a pinch of salt.
2. Dice the tomato and add it to the eggs.
3. Cook in a dry pan until set, then top with cheese.
"""

JUDGE_SYSTEM_RULES = """
You are an expert AI judge evaluating a recipe-writing model.
Review the original recipe context, available ingredients, and the generated output.

Check if the model followed these rules:
1. Did it use ONLY the available ingredients (plus water, salt, and pepper)? No unauthorized oils, butters, or extra ingredients.
2. Are all original ingredients that were missing from the available list accurately documented as either '<ingredient> omitted' or '<ingredient> replaced with <X>' (where X is available)?
3. Do the Steps section completely avoid mentioning any omitted or replaced ingredients?
4. Is the output formatted strictly as 'Changes:' followed by bullet points, and 'Steps:' followed by numbered steps?

Provide your evaluation in EXACTLY this format:
Result: PASS or FAIL
Explanation: 1-2 sentence explanation of any violations or confirmation of success
"""


# ---------- 1. Generation ----------

def generate_recipe(available_ingredients: str, retrieved_context: str,
                    missing_ingredients=None, model: str = GEN_MODEL) -> str:
    missing_line = ""
    if missing_ingredients is not None:
        missing_line = "Missing ingredients: " + (", ".join(missing_ingredients) or "none") + "\n\n"
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": BASE_SYSTEM_RULES},
            {
                "role": "user",
                "content": (
                    f"Available ingredients: {available_ingredients}\n\n"
                    f"{retrieved_context}\n\n"
                    f"{missing_line}"
                    "First list which original ingredients are unavailable under Changes, then write the Steps:"
                ),
            },
        ],
        options={"temperature": 0.1},
    )
    return response.message.content


# ---------- 2. Code-based check (deterministic, runs before the LLM judge) ----------

def _split_sections(output: str):
    """Return (changes_text, steps_text) from the model output."""
    m = re.search(r"steps\s*:", output, flags=re.I)
    steps = output[m.end():] if m else ""
    head = output[:m.start()] if m else output
    c = re.search(r"changes\s*:", head, flags=re.I)
    changes = head[c.end():] if c else ""
    return changes, steps


def _mentions(text: str, ingredient: str) -> bool:
    """Whole-word match on the normalized ingredient (also catches simple plurals)."""
    ing = normalize_ingredient(ingredient)
    return re.search(rf"\b{re.escape(ing)}(e?s)?\b", text.lower()) is not None


def check_output(output: str, available, original_ingredients) -> list:
    """Return a list of problems. Empty list means the output passes."""
    problems = []
    available_set = set(normalize_ingredients(available))
    changes, steps = _split_sections(output)

    if not changes.strip():
        problems.append("Missing 'Changes:' section")
    if not steps.strip():
        problems.append("Missing 'Steps:' section")
    if problems:
        return problems

    # Parse Changes lines
    removed, replacements = [], {}
    for line in changes.splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        m = re.match(r"(.+?)\s+replaced with\s+(.+)", line, flags=re.I)
        if m:
            replacements[m.group(1).strip()] = m.group(2).strip()
            continue
        m = re.match(r"(.+?)\s+omitted", line, flags=re.I)
        if m:
            removed.append(m.group(1).strip())

    # Replacement must be an available ingredient
    for old, new in replacements.items():
        if normalize_ingredient(new) not in available_set:
            problems.append(f"'{old}' replaced with unavailable ingredient '{new}'")

    # Every missing original ingredient must be documented
    documented = {normalize_ingredient(i) for i in list(removed) + list(replacements)}
    for ing in normalize_ingredients(original_ingredients):
        if ing not in available_set and ing not in documented:
            problems.append(f"Missing ingredient '{ing}' not listed in Changes")

    # Steps must not mention omitted/replaced ingredients
    for ing in list(removed) + list(replacements):
        if _mentions(steps, ing):
            problems.append(f"Steps mention removed ingredient '{ing}'")

    # Steps must not add available ingredients that aren't in the original recipe
    original_set = set(normalize_ingredients(original_ingredients))
    replacement_targets = {normalize_ingredient(v) for v in replacements.values()}
    for ing in available_set - original_set - replacement_targets:
        if _mentions(steps, ing):
            problems.append(f"Steps add '{ing}', which is not in the original recipe")

    # Steps must not use obvious off-list ingredients (oil/butter unless available)
    for banned in ("oil", "butter"):
        if banned not in available_set and _mentions(steps, banned):
            problems.append(f"Steps use '{banned}', which is not available")

    return problems


# ---------- 3. LLM-as-a-judge ----------

def evaluate_generation(ingredients: str, retrieved_context: str, generated_output: str,
                        model: str = JUDGE_MODEL) -> str:
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_RULES},
            {
                "role": "user",
                "content": (
                    f"Available ingredients: {ingredients}\n\n"
                    f"Context provided to model:\n{retrieved_context}\n\n"
                    f"Generated output to evaluate:\n{generated_output}\n\n"
                    "Evaluate the generated output:"
                ),
            },
        ],
        options={"temperature": 0.0},
    )
    return response.message.content


def judge_passed(verdict: str) -> bool:
    return re.search(r"result\s*:\s*\**\s*pass", verdict, flags=re.I) is not None

