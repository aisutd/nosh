import os
import requests
from pathlib import Path
from dotenv import load_dotenv


# Load .env from repository root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000"
)


def ask_rag(question, recipe_context=None):
    """
    Sends the user's question to the NOSH backend/RAG system.
    """

    payload = {
        "question": question
    }

    # Include existing recipe context if we already have one
    if recipe_context:
        payload["context"] = recipe_context

    try:
        response = requests.post(
            f"{BACKEND_URL}/query",
            json=payload,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "response",
            "I could not find an answer."
        )

    except requests.exceptions.ConnectionError:
        return "The NOSH backend is currently unavailable."

    except requests.exceptions.Timeout:
        return "The NOSH backend took too long to respond."

    except Exception as error:
        print("Backend error:", error)
        return "Something went wrong while contacting the recipe system."
if __name__ == "__main__":
    print(ask_rag("How do I cook pasta?"))