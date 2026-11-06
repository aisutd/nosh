"""Calls the NOSH RAG pipeline directly so the voice agent doesn't need a running backend."""
import sys
from pathlib import Path

# Add repo root to sys.path so we can import retrieval/, llm/, etc.
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "Backend"

sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(REPO_ROOT))

from nosh_pipeline import run_nosh


def ask_rag(question, available_ingredients=None, recipe_context=None):
    """Call the NOSH RAG pipeline directly (no HTTP backend needed)."""
    result = run_nosh(
        available_ingredients or "",
        user_query=question,
    )
    if result["status"] == "ok":
        return result["recipe"]
    return result.get("message", "I could not find a recipe for that.")


if __name__ == "__main__":
    print(ask_rag("How do I cook pasta?", available_ingredients="pasta, garlic, olive oil"))
