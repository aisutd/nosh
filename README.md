# NOSH

## Description

NOSH is an AI-powered student cooking assistant that turns ingredients from a refrigerator photo into practical, budget-friendly meals. It combines ingredient detection, recipe retrieval, and a hands-free voice interface for substitutions, timers, and step-by-step cooking guidance.

## Planned Technologies

- Python and JavaScript/TypeScript
- React and Tailwind CSS
- FastAPI or Flask with MongoDB and Redis
- YOLOv8, OpenCV, LangChain, RAG, vector search, speech-to-text, and text-to-speech

## Docker Setup

Make sure Docker Desktop is installed and running.

```bash
docker compose up -d
docker compose down
docker compose ps
```

This is a generic starter configuration. The team can add project-specific dependencies and startup commands later.
## Voice Agent

The NOSH Voice Agent provides hands-free interaction for students while cooking.

### Current Prototype

The current prototype supports:

- Speech-to-text using Deepgram Nova-3
- Text-to-speech using the macOS `say` command
- Step-by-step recipe navigation
- Voice commands such as:
  - Start cooking
  - Next step
  - Repeat
  - Go back
  - Stop
- Basic cooking-related questions
- Spoken recipe instructions

### Voice Agent Flow

```text
User Speech
    |
    v
Microphone
    |
    v
Audio Recording
    |
    v
Deepgram Nova-3
Speech-to-Text
    |
    v
Transcribed Text
    |
    v
NOSH Voice Agent
    |
    +---- Voice Command
    |        |
    |        v
    |    Recipe Navigation
    |
    +---- Cooking Question
             |
             v
       Recipe Response
             |
             v
       Text-to-Speech
             |
             v
          User