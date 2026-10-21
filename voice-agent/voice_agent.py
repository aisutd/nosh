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
# RECIPE STATE (populated at startup via RAG)
# -----------------------------------

recipe_name = ""
recipe_steps = []
recipe_context = ""
current_step = 0


def parse_recipe(rag_response):
    """Pull name and steps out of the LLM's structured response.

    Expected format:
        Recipe Name: <name>
        Changes:
        - none
        Steps:
        1. <step>
        2. <step>
    """
    import re
    name = ""
    steps = []

    name_match = re.search(r"Recipe Name:\s*(.+)", rag_response)
    if name_match:
        name = name_match.group(1).strip()

    steps = re.findall(r"^\d+\.\s+(.+)", rag_response, re.MULTILINE)

    return name, steps


def fetch_recipe(ingredients):
    """Call RAG with the user's ingredients and return (name, steps, full_text)."""
    speak("Looking up a recipe for you, one moment.")
    response = ask_rag(
        "Find me a recipe I can make",
        available_ingredients=ingredients,
    )
    name, steps = parse_recipe(response)
    return name, steps, response


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
    """Answer simple questions from the current recipe context without calling RAG."""
    question = question.lower()

    if "what recipe" in question or "what are we making" in question:
        return f"We are currently making {recipe_name}."

    if "ingredient" in question:
        return f"The recipe context has the full ingredient list: {recipe_context[:300]}"

    if "what step" in question or "current step" in question:
        return (
            f"You are on step {current_step + 1}. "
            f"{recipe_steps[current_step]}"
        )

    if "how many steps" in question:
        return f"This recipe has {len(recipe_steps)} steps."

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
        available_ingredients=ingredients_input,
        recipe_context=recipe_context,
    )

    return rag_answer


# -----------------------------------
# START VOICE AGENT
# -----------------------------------

speak(
    "Welcome to Nosh. "
    "Please say the ingredients you have available."
)

# Listen for ingredients and fetch a recipe before entering the main loop
ingredients_input = listen()
recipe_name, recipe_steps, recipe_context = fetch_recipe(ingredients_input)

if not recipe_steps:
    speak("I could not find a recipe for those ingredients. Please restart and try again.")
    exit()

speak(
    f"I found a recipe for {recipe_name}. "
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