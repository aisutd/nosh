import os
from pathlib import Path

import sounddevice as sd
from scipy.io.wavfile import write
from dotenv import load_dotenv
from deepgram import DeepgramClient


SAMPLE_RATE = 16000
DURATION = 5
AUDIO_FILE = "recording.wav"

# Load .env from repo root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

API_KEY = os.getenv("DEEPGRAM_API_KEY")

if not API_KEY:
    raise ValueError("DEEPGRAM_API_KEY not found in .env")

deepgram = DeepgramClient(api_key=API_KEY)

print("Recording for 5 seconds...")
print("Speak now!")

audio = sd.rec(
    int(DURATION * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="int16"
)

sd.wait()

write(AUDIO_FILE, SAMPLE_RATE, audio)

print("Recording finished.")
print("Sending audio to Deepgram Nova-3...")

with open(AUDIO_FILE, "rb") as file:
    audio_data = file.read()

response = deepgram.listen.v1.media.transcribe_file(
    request=audio_data,
    model="nova-3",
    language="en-US",
    smart_format=True
)

transcript = (
    response.results.channels[0]
    .alternatives[0]
    .transcript
)

print("\nYou said:")
print(transcript)