import os
import string
import subprocess
from pathlib import Path

import sounddevice as sd
from scipy.io.wavfile import write
from dotenv import load_dotenv
from deepgram import DeepgramClient

from rag_client import generate_recipe


SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = "recording.wav"


# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not API_KEY:
    raise ValueError(
        "DEEPGRAM_API_KEY was not found. "
        "Make sure your .env file is in the repository root."
    )

deepgram = DeepgramClient(api_key=API_KEY)


# ---------------------------------------------------------
# Voice-agent state
# ---------------------------------------------------------

user_ingredients = []

current_recipe = None
current_recipe_steps = []
current_step = 0


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def clean_ingredient(ingredient):
    ingredient = ingredient.strip().lower()

    ingredient = ingredient.translate(
        str.maketrans("", "", string.punctuation)
    )

    return ingredient.strip()


# ---------------------------------------------------------
# Speech to Text
# ---------------------------------------------------------

def listen():
    print("\nListening... Speak now!")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    write(
        AUDIO_FILE,
        SAMPLE_RATE,
        audio
    )

    print("Sending audio to Deepgram Nova-3...")

    with open(AUDIO_FILE, "rb") as file:
        audio_data = file.read()

    response = deepgram.listen.v1.media.transcribe_file(
        request=audio_data,
        model="nova-3",
        language="en-US",
        smart_format=True
    )

    command = (
        response.results.channels[0]
        .alternatives[0]
        .transcript
        .strip()
        .lower()
    )

    print("You said:", command)

    return command


# ---------------------------------------------------------
# Text to Speech
# ---------------------------------------------------------

def speak(text):
    print("NOSH:", text)

    subprocess.run(
        ["say", str(text)]
    )


# ---------------------------------------------------------
# Ingredient handling
# ---------------------------------------------------------

def add_ingredient(ingredient):
    ingredient = clean_ingredient(ingredient)

    if not ingredient:
        return "Please tell me which ingredient to add."

    if ingredient in user_ingredients:
        return f"{ingredient} is already in your ingredient list."

    user_ingredients.append(ingredient)

    print("Current ingredients:", user_ingredients)

    return f"Added {ingredient}."


def remove_ingredient(ingredient):
    ingredient = clean_ingredient(ingredient)

    if not ingredient:
        return "Please tell me which ingredient to remove."

    if ingredient not in user_ingredients:
        return f"{ingredient} is not in your ingredient list."

    user_ingredients.remove(ingredient)

    print("Current ingredients:", user_ingredients)

    return f"Removed {ingredient}."


def list_ingredients():
    if not user_ingredients:
        return "You have not added any ingredients yet."

    return (
        "Your ingredients are "
        + ", ".join(user_ingredients)
        + "."
    )


def clear_ingredients():
    user_ingredients.clear()

    print("Current ingredients:", user_ingredients)

    return "I cleared your ingredient list."


# ---------------------------------------------------------
# RAG recipe generation
# ---------------------------------------------------------

def request_recipe(command):
    global current_recipe
    global current_recipe_steps
    global current_step

    if not user_ingredients:
        return (
            "Please add some ingredients before "
            "asking me to generate a recipe."
        )

    print("\nSending request to NOSH RAG...")
    print("Ingredients:", user_ingredients)
    print("User query:", command)

    result = generate_recipe(
        user_ingredients,
        user_query=command
    )

    if not result.get("success"):
        return result.get(
            "message",
            "I could not generate a recipe."
        )

    current_recipe = result.get("recipe")

    if not current_recipe:
        return "The backend returned no recipe."

    print("\nRAG RESPONSE:")
    print(current_recipe)

    source = result.get("source_recipe")

    if source:
        print("Source recipe:", source)

    current_step = 0

    current_recipe_steps = [
        line.strip()
        for line in str(current_recipe).split("\n")
        if line.strip()
    ]

    return (
        "I generated a recipe for you. "
        + str(current_recipe)
    )


# ---------------------------------------------------------
# Current recipe context
# ---------------------------------------------------------

def handle_recipe_context(command):
    global current_step

    if not current_recipe:
        return None

    if (
        "repeat" in command
        and current_recipe_steps
    ):
        return current_recipe_steps[current_step]

    if (
        "next" in command
        and current_recipe_steps
    ):
        if current_step < len(current_recipe_steps) - 1:
            current_step += 1
            return current_recipe_steps[current_step]

        return "You are at the end of the recipe."

    if (
        "back" in command
        or "previous" in command
    ):
        if current_recipe_steps and current_step > 0:
            current_step -= 1
            return current_recipe_steps[current_step]

        return "You are already at the beginning."

    if (
        "what recipe" in command
        or "repeat the recipe" in command
    ):
        return str(current_recipe)

    return None


# ---------------------------------------------------------
# Main program
# ---------------------------------------------------------

speak(
    "Welcome to Nosh. "
    "Tell me what ingredients you have."
)


while True:

    try:

        command = listen()

        if not command:
            speak(
                "I did not hear anything. "
                "Please try again."
            )
            continue


        # -------------------------------------------------
        # Stop
        # -------------------------------------------------

        if (
            "stop cooking" in command
            or "stop cooking mode" in command
            or command == "stop"
            or command == "exit"
        ):
            speak("Cooking mode stopped.")
            break


        # -------------------------------------------------
        # Help
        # -------------------------------------------------

        elif "help" in command:

            speak(
                "You can say I have garlic, "
                "add pasta, remove onions, "
                "what ingredients do I have, "
                "clear ingredients, "
                "what can I cook, "
                "make me something quick, "
                "next step, repeat, "
                "go back, "
                "or stop cooking."
            )


        # -------------------------------------------------
        # Add ingredient
        # -------------------------------------------------

        elif command.startswith("i have "):

            ingredient = command.replace(
                "i have ",
                "",
                1
            )

            speak(
                add_ingredient(ingredient)
            )


        elif command.startswith("add "):

            ingredient = command.replace(
                "add ",
                "",
                1
            )

            speak(
                add_ingredient(ingredient)
            )


        # -------------------------------------------------
        # Remove ingredient
        # -------------------------------------------------

        elif command.startswith("remove "):

            ingredient = command.replace(
                "remove ",
                "",
                1
            )

            speak(
                remove_ingredient(ingredient)
            )


        # -------------------------------------------------
        # Clear ingredients
        # -------------------------------------------------

        elif (
            "clear ingredients" in command
            or "clear my ingredients" in command
        ):

            speak(
                clear_ingredients()
            )


        # -------------------------------------------------
        # Ingredient list
        # -------------------------------------------------

        elif (
            "what ingredients" in command
            or "list ingredients" in command
            or "what do i have" in command
        ):

            speak(
                list_ingredients()
            )


        # -------------------------------------------------
        # Current recipe navigation
        # -------------------------------------------------

        else:

            context_response = (
                handle_recipe_context(command)
            )

            if context_response:
                speak(context_response)
                continue


            # ---------------------------------------------
            # Send cooking requests to RAG
            # ---------------------------------------------

            if (
                "what can i cook" in command
                or "what can i make" in command
                or "make me" in command
                or "generate" in command
                or "recipe" in command
                or "cook" in command
            ):

                response = request_recipe(command)

                speak(response)

                continue


            # ---------------------------------------------
            # Fallback
            # ---------------------------------------------

            speak(
                "I understood what you said, "
                "but I am not sure which cooking action "
                "you want me to perform."
            )


    except KeyboardInterrupt:

        print("\nVoice agent stopped.")
        break


    except Exception as error:

        print("Error:", error)

        speak(
            "Something went wrong while "
            "processing your voice."
        )