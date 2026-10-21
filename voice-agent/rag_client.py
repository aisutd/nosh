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