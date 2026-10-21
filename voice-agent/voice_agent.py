import os
import subprocess
from pathlib import Path

import sounddevice as sd
from scipy.io.wavfile import write
from dotenv import load_dotenv
from deepgram import DeepgramClient

from rag_client import ask_rag


# -----------------------------------
# SETTINGS
# -----------------------------------

SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = "recording.wav"


# -----------------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------------

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not API_KEY:
    raise ValueError(
        "DEEPGRAM_API_KEY was not found. "
        "Make sure your .env file is in the repository root."
    )


# -----------------------------------
# DEEPGRAM
# -----------------------------------

deepgram = DeepgramClient(api_key=API_KEY)


# -----------------------------------
# SAMPLE RECIPE / CACHED CONTEXT
# -----------------------------------

recipe_name = "Spaghetti Aglio e Olio"

recipe_ingredients = [
    "spaghetti",
    "one fourth cup olive oil",
    "four cloves of garlic",
    "salt",
    "optional red pepper flakes"
]

recipe_steps = [
    "Bring a large pot of water to a boil.",
    "Add the pasta and cook for about ten minutes, or until al dente.",
    "Heat olive oil in a pan over medium heat.",
    "Add four cloves of chopped garlic and cook until lightly golden.",
    "Drain the pasta and add it to the pan.",
    "Toss everything together and serve."
]

recipe_context = f"""
Recipe: {recipe_name}

Ingredients:
- Spaghetti
- One fourth cup olive oil
- Four cloves of garlic
- Salt
- Optional red pepper flakes

Cooking instructions:
1. Bring a large pot of water to a boil.
2. Add the pasta and cook for about ten minutes, or until al dente.
3. Heat olive oil in a pan over medium heat.
4. Add four cloves of chopped garlic and cook until lightly golden.
5. Drain the pasta and add it to the pan.
6. Toss everything together and serve.
"""

current_step = 0


# -----------------------------------
# SPEECH TO TEXT
# -----------------------------------

def listen():
    print("\nListening... Speak now!")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    write(AUDIO_FILE, SAMPLE_RATE, audio)

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


# -----------------------------------
# TEXT TO SPEECH
# -----------------------------------

def speak(text):
    print("NOSH:", text)

    subprocess.run(
        ["say", text]
    )


# -----------------------------------
# CHECK CURRENT RECIPE CONTEXT
# -----------------------------------

def answer_from_recipe_context(question):
    """
    Check whether the current recipe already contains
    enough information to answer the user's question.

    If yes, return an answer.

    If not, return None so we can ask the backend/RAG.
    """

    question = question.lower()

    if "ingredient" in question:
        return (
            "For this recipe you need spaghetti, "
            "one fourth cup of olive oil, four cloves of garlic, "
            "salt, and optional red pepper flakes."
        )

    if "how much garlic" in question:
        return "The recipe uses four cloves of garlic."

    if "how much olive oil" in question:
        return "The recipe uses one fourth cup of olive oil."

    if (
        "how long" in question
        or "cooking time" in question
        or "how many minutes" in question
    ):
        return (
            "Cook the pasta for about ten minutes, "
            "or until it is al dente."
        )

    if (
        "what heat" in question
        or "what temperature" in question
    ):
        return "Use medium heat when cooking the garlic."

    if "what recipe" in question:
        return f"We are currently making {recipe_name}."

    if "what step" in question:
        return (
            f"You are currently on step {current_step + 1}. "
            f"{recipe_steps[current_step]}"
        )

    if "how many steps" in question:
        return (
            f"This recipe has {len(recipe_steps)} steps."
        )

    return None


# -----------------------------------
# HANDLE USER QUESTION
# -----------------------------------

def handle_question(question):
    # First check cached recipe context
    context_answer = answer_from_recipe_context(question)

    if context_answer:
        print("Answer found in current recipe context.")
        return context_answer

    # If not available locally, send question to backend/RAG
    print("Answer not found in cached context.")
    print("Sending question to backend/RAG...")

    rag_answer = ask_rag(
        question,
        recipe_context=recipe_context
    )

    return rag_answer


# -----------------------------------
# START VOICE AGENT
# -----------------------------------

speak(
    "Welcome to Nosh cooking mode. "
    "Say start cooking when you are ready."
)


while True:

    try:
        command = listen()

        # No speech detected
        if not command:
            speak(
                "I did not hear anything. Please try again."
            )
            continue


        # -----------------------------------
        # LOCAL VOICE COMMANDS
        # -----------------------------------

        if "start" in command:

            current_step = 0

            speak(
                f"Starting {recipe_name}. "
                f"Step 1. {recipe_steps[current_step]}"
            )


        elif "next" in command:

            if current_step < len(recipe_steps) - 1:

                current_step += 1

                speak(
                    f"Step {current_step + 1}. "
                    f"{recipe_steps[current_step]}"
                )

            else:

                speak(
                    "You have completed the recipe."
                )


        elif "repeat" in command:

            speak(
                f"Step {current_step + 1}. "
                f"{recipe_steps[current_step]}"
            )


        elif (
            "back" in command
            or "previous" in command
        ):

            if current_step > 0:

                current_step -= 1

                speak(
                    f"Step {current_step + 1}. "
                    f"{recipe_steps[current_step]}"
                )

            else:

                speak(
                    "You are already on the first step."
                )


        elif "help" in command:

            speak(
                "You can say start cooking, next step, "
                "repeat, go back, ask a cooking question, "
                "or say stop cooking."
            )


        elif (
            "stop" in command
            or "exit" in command
        ):

            speak(
                "Cooking mode stopped."
            )

            break


        # -----------------------------------
        # COOKING QUESTION
        # -----------------------------------

        else:

            response = handle_question(command)

            speak(response)


    except KeyboardInterrupt:

        print("\nVoice agent stopped.")

        break


    except Exception as error:

        print("Error:", error)

        speak(
            "Something went wrong while processing your voice."
        )