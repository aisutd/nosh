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


### Client modes after integration

The desktop agent retains ingredient add/remove/list/clear commands and uses
`voice-agent/rag_client.py`'s `generate_recipe()` HTTP adapter by default. Set
`BACKEND_URL` to select the running backend. Install its audio dependencies with
`python -m pip install -r voice-agent/requirements.txt`.

For a standalone run without FastAPI, install the repository-root RAG dependencies
as well and set `NOSH_RAG_MODE=direct`. Both modes return the same result shape to
the desktop agent. The `ask_rag(question, available_ingredients, recipe_context)`
interface from Mock_Main remains available and calls the standalone pipeline
directly. Neither HTTP imports nor desktop microphone initialization are triggered
by importing the client module.

The Week 4–6 integrated web app remains under `nosh-backend/`; the root Backend
and Frontend directories brought in from Mock_Main are preserved separately.
