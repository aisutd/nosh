import os
import subprocess
from pathlib import Path

import sounddevice as sd
from scipy.io.wavfile import write
from dotenv import load_dotenv
from deepgram import DeepgramClient


SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = "recording.wav"

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not API_KEY:
    raise ValueError(
        "DEEPGRAM_API_KEY was not found. "
        "Make sure your .env file is in the repository root."
    )

deepgram = DeepgramClient(api_key=API_KEY)

recipe_steps = [
    "Bring a large pot of water to a boil.",
    "Add the pasta and cook until al dente.",
    "Heat olive oil in a pan over medium heat.",
    "Add chopped garlic and cook until lightly golden.",
    "Drain the pasta and add it to the pan.",
    "Toss everything together and serve."
]

current_step = 0


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


def speak(text):
    print("NOSH:", text)
    subprocess.run(["say", text])


def answer_cooking_question(command):
    if "what ingredients" in command:
        return (
            "You will need spaghetti, olive oil, garlic, salt, "
            "and optional red pepper flakes."
        )

    elif "how much garlic" in command:
        return "Use about four cloves of garlic."

    elif "how much olive oil" in command:
        return "Use about one fourth cup of olive oil."

    elif "how long" in command or "cooking time" in command:
        return "Cook the pasta for about ten minutes, or until al dente."

    elif "what temperature" in command or "what heat" in command:
        return "Use medium heat when cooking the garlic."

    return None


speak("Welcome to Nosh cooking mode.")

while True:
    try:
        command = listen()

        if not command:
            speak("I did not hear anything. Please try again.")
            continue

        if "start" in command:
            current_step = 0
            speak(recipe_steps[current_step])

        elif "next" in command:
            if current_step < len(recipe_steps) - 1:
                current_step += 1
                speak(recipe_steps[current_step])
            else:
                speak("You have completed the recipe.")

        elif "repeat" in command:
            speak(recipe_steps[current_step])

        elif "back" in command or "previous" in command:
            if current_step > 0:
                current_step -= 1
                speak(recipe_steps[current_step])
            else:
                speak("You are already on the first step.")

        elif "stop" in command or "exit" in command:
            speak("Cooking mode stopped.")
            break

        else:
            answer = answer_cooking_question(command)

            if answer:
                speak(answer)
            else:
                speak("Sorry, I did not understand that question.")

    except Exception as error:
        print("Error:", error)
        speak("Something went wrong while processing your voice.")