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
