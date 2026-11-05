import os
import requests
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000"
)


def generate_recipe(ingredients, user_query=""):
    # HTTP remains the default for the integrated web/backend workflow.
    # The standalone direct pipeline is available without starting FastAPI.
    if os.getenv("NOSH_RAG_MODE", "http").lower() == "direct":
        return _direct_result(ingredients, user_query)
    payload = {
        "ingredients": ingredients,
        "user_query": user_query
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/recipes/generate",
            json=payload,
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        result = data.get("result", {})

        if result.get("status") == "ok":
            return {
                "success": True,
                "recipe": result.get("recipe"),
                "source_recipe": result.get("source_recipe"),
                "source_url": result.get("source_url")
            }

        return {
            "success": False,
            "message": result.get(
                "message",
                "No recipe could be generated."
            )
        }

    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "message": "The NOSH backend is unavailable."
        }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "The recipe system took too long to respond."
        }

    except Exception as error:
        print("Backend error:", error)

        return {
            "success": False,
            "message": "Something went wrong while contacting NOSH."
        }


def _direct_result(ingredients, user_query):
    """Load the standalone pipeline only when explicitly requested."""
    import sys
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from nosh_pipeline import run_nosh
    result = run_nosh(ingredients, user_query=user_query)
    if result.get("status") == "ok":
        return {"success": True, "recipe": result.get("recipe"),
                "source_recipe": result.get("source_recipe"),
                "source_url": result.get("source_url")}
    return {"success": False, "message": result.get("message", "I could not find a recipe for that.")}


def ask_rag(question, available_ingredients=None, recipe_context=None):
    """Preserve Mock_Main's direct-client API for standalone callers.

    recipe_context is retained for signature compatibility with Mock_Main.
    Retrieval and source validation remain the standalone pipeline's responsibility.
    """
    result = _direct_result(available_ingredients or "", question)
    return result.get("recipe") if result["success"] else result["message"]
