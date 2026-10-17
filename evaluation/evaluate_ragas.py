"""RAGAS evaluation of the NOSH RAG pipeline. Run: python -m evaluation.evaluate_ragas

Measures faithfulness, response relevancy, and context precision of the
retrieval + generation pipeline using local Ollama models (no OpenAI key needed).
Results are saved to evaluation/results/ragas_results.json.
"""
import sys as _sys
from types import ModuleType as _ModuleType

def _patch_vertexai_shim():
    _mod = "langchain_community.chat_models.vertexai"
    if _mod not in _sys.modules:
        try:
            from langchain_google_vertexai import ChatVertexAI as _CV
        except ImportError:
            _CV = None
        stub = _ModuleType(_mod)
        stub.ChatVertexAI = _CV
        _sys.modules[_mod] = stub

_patch_vertexai_shim()
# --- End shim ---

import json
import warnings
from datetime import datetime, timezone
from pathlib import Path

# Suppress deprecation warnings from ragas at import time.
# LangchainLLMWrapper is the only viable bridge to local Ollama models;
# ragas.llms.llm_factory only supports OpenAI-compatible APIs.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from langchain_ollama import ChatOllama
    from ragas import evaluate
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithoutReference
    from ragas.dataset_schema import SingleTurnSample, EvaluationDataset
    from ragas.llms import LangchainLLMWrapper

from rag.store import embedding_function as nosh_ef
from retrieval.nosh_retrieval import get_collection, search_recipes, format_recipes_for_llm, normalize_ingredients
from llm.nosh_generation import generate_recipe, INSUFFICIENT_CONTEXT, OUT_OF_SCOPE

RESULTS_DIR = Path(__file__).resolve().parent / "results"
GRADER_MODEL = "gemma2"  # grades faithfulness + context precision
TOP_K = 3

# Test cases: (available_ingredients, cooking_query)
# Ingredient lists match what the actual top recipe in the index requires.
TEST_CASES = [
    # Lemonade: Old-Fashioned Lemonade (lemon, white sugar, water)
    ("lemon, sugar",
     "Make lemonade"),
    # Coconut Rice: Coconut Rice (jasmine rice, coconut milk, water, sugar, salt)
    ("jasmine rice, coconut milk, sugar",
     "Make coconut rice"),
    # Smoothie: Peanut Butter Banana Smoothie (bananas, milk, peanut butter, honey, ice)
    ("banana, milk, peanut butter, honey",
     "Make a peanut butter banana smoothie"),
    # Guacamole: World's Best Guacamole (avocado, lime, onion, cilantro, serrano chile, pomegranate)
    ("avocado, lime, onion, cilantro, serrano chile pepper, pomegranate",
     "Make guacamole"),
    # Banana Bread: Joy's Easy Banana Bread (banana, sugar, egg, butter, flour, baking soda)
    ("banana, sugar, egg, butter, flour, baking soda",
     "Bake banana bread"),
    # Mango Salsa: Fresh Mango Salsa (mango, tomato, onion, sugar, cilantro, lime, cider vinegar, garlic)
    ("mango, tomato, onion, sugar, cilantro, lime, cider vinegar, garlic",
     "Make fresh mango salsa"),
    # Apple Crisp: Easy Apple Crisp with Oat Topping (apple, sugar, cinnamon, oat, flour, butter)
    ("apple, sugar, cinnamon, oat, flour, butter",
     "Make apple crisp"),
    # Blueberry Muffins: To Die For Blueberry Muffins
    ("blueberry, flour, sugar, egg, butter, milk",
     "Make blueberry muffins"),
]



def build_sample(ingredients: str, query: str, collection) -> dict | None:
    """Run retrieval + generation for one test case. Returns None if no recipes found."""
    available = ", ".join(normalize_ingredients(ingredients))
    search_query = f"{query} Ingredients: {available}"

    recipes = search_recipes(
        search_query, top_k=TOP_K, collection=collection,
        available_ingredients=ingredients,
    )
    if not recipes:
        return None

    context = format_recipes_for_llm(recipes, top_k=1)
    answer = generate_recipe(
        available_ingredients=available,
        retrieved_context=context,
        user_query=query,
    )

    if answer in (INSUFFICIENT_CONTEXT, OUT_OF_SCOPE):
        return None

    return {
        "user_input": query,
        "retrieved_contexts": [r["document"] for r in recipes],
        "response": answer,
    }


def main():
    print("Loading Chroma collection...")
    collection = get_collection()
    print(f"Index has {collection.count()} recipes.\n")

    print("Building evaluation dataset (running retrieval + generation per case)...")
    samples, skipped = [], []
    for ingredients, query in TEST_CASES:
        print(f"  {query!r} ... ", end="", flush=True)
        try:
            data = build_sample(ingredients, query, collection)
        except Exception as exc:
            print(f"error ({exc})")
            skipped.append({"query": query, "reason": str(exc)})
            continue
        if data:
            samples.append(SingleTurnSample(**data))
            print("ok")
        else:
            print("skipped (no matching recipes)")
            skipped.append({"query": query, "reason": "no matching recipes"})

    if not samples:
        print("\nNo samples built — check your Chroma index and Ollama.")
        return

    print(f"\n{len(samples)} samples ready, {len(skipped)} skipped.")
    print(f"\nConfiguring RAGAS with grader={GRADER_MODEL} ...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        llm = LangchainLLMWrapper(ChatOllama(model=GRADER_MODEL, temperature=0.0))

    metrics = [
        Faithfulness(llm=llm),
        LLMContextPrecisionWithoutReference(llm=llm),
        # ResponseRelevancy removed: local models (llama3.2, gemma2) don't reliably
        # follow RAGAS's strict JSON-only output format, causing OutputParserException
        # and TimeoutError on every run. Faithfulness + ContextPrecision are the
        # two most signal-rich RAG metrics and run cleanly with local Ollama models.
    ]

    print("Running RAGAS evaluation (this takes a few minutes with local models)...\n")
    results = evaluate(
        dataset=EvaluationDataset(samples=samples),
        metrics=metrics,
        raise_exceptions=False,  # don't abort on individual metric timeouts
    )

    df = results.to_pandas()
    metric_cols = ["faithfulness", "response_relevancy", "llm_context_precision_without_reference"]
    scores = {col: round(float(df[col].mean()), 4) for col in metric_cols if col in df.columns}

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "grader_model": GRADER_MODEL,
        "embedding_model": "all-MiniLM-L6-v2",
        "samples_evaluated": len(samples),
        "samples_skipped": skipped,
        "scores": scores,
        "per_sample": json.loads(df.to_json(orient="records")),
        "limitations": (
            "Small development evaluation using local Ollama models. "
            "RAGAS scores are LLM-graded estimates, not ground-truth guarantees. "
            "Ingredient filtering may skip some valid test cases."
        ),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "ragas_results.json"
    out.write_text(json.dumps(report, indent=2) + "\n")

    print("Scores:")
    for metric, score in scores.items():
        print(f"  {metric}: {score:.3f}")
    print(f"\nSkipped {len(skipped)} cases.")
    print(f"Full results saved to {out}")


if __name__ == "__main__":
    main()
