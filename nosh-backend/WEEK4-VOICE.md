# Week 4 frontend voice integration

The pantry and both cooking views now include Cook with NOSH. The browser transcribes speech and sends the final transcript to `POST /voice/turn`. NOSH displays the answer and optionally speaks it using browser speech synthesis. No API keys are sent to the browser. The separate desktop Deepgram agent remains available in the sibling `nosh/voice-agent` project.

## Try it

Start the backend using the existing project setup (`uvicorn main:app --reload` from `Backend`) and the frontend (`npm ci`, then `npm run dev` from `Frontend`). The backend still requires its configured MongoDB, Ollama models and built recipe index. Open `http://localhost:5173/pantry` in a browser supporting SpeechRecognition (such as Chrome), add ingredients and allow microphone access.

- Say “What can I cook?” to use the existing RAG generation pipeline with pantry ingredients.
- Open a selected or saved recipe to ask questions about that recipe.
- Say “start cooking”, “next step”, “previous step”, “repeat”, or “go to step 2”. Numbered instructions are required for navigation.
- Ask a cooking question: the backend uses existing recipe_chat generation and its judge. Failed validation never displays the draft.
- Stop listening cancels capture; Stop speaking interrupts the reply. Each tap captures one utterance. Listening does not restart automatically while NOSH speaks.
- Type a question when speech recognition is unavailable. Errors preserve the question for retry.

Microphones require HTTPS or localhost; an ordinary HTTP LAN address cannot use the mic. Browser speech recognition availability and processing depend on the browser/provider, and may require an internet connection. Existing API CORS origins must match the frontend deployment. Voice API requests default to the page hostname on port 8000; set `VITE_API_URL` for a different backend, using HTTPS when the frontend uses HTTPS.

Recipe and step state belongs to the mounted assistant and resets when leaving the page. There is no shared global cooking session or durable voice history. The endpoint treats browser recipe text as untrusted context; it does not authorize changes or saves. Existing recipe saving controls remain available. No new recipe is generated merely because a question cannot be answered.

## Existing pipeline repair

Before this change, the working copy of `Backend/nosh_pipeline.py` contained desktop microphone code, missing `run_nosh` required by the API. Its full original contents were preserved at `local-backups/nosh_pipeline.before-week4.py` (ignored by Git). The API pipeline was restored from this repository's HEAD. Existing edits to `Backend/llm/nosh_generation.py` and `Backend/requirements.txt` were preserved.

## Verification

Backend routing tests: from `Backend`, run `python -m unittest discover -s tests -p test_voice.py -v` with FastAPI and httpx installed. These tests exercise actual HTTP validation and routing, with test-only RAG/LLM fakes.

Frontend: `npm run build`. A separate `Frontend/tests/voice-smoke.cjs` Playwright script tests mic transcripts, typed input, request state, failures, denial, unsupported browsers and mobile layout against test-only browser/API doubles. Run with Vite on port 5173, Playwright installed (or NODE_PATH set), and Chrome installed; `PLAYWRIGHT_CHANNEL` can select another installed browser channel. No doubles or service bypasses are imported by production code.

In the implementation environment, the production build, changed-component lint checks and five backend tests passed. An in-app browser check also verified typed input, the unavailable-backend retry path, and a displayed response from the actual voice route running in an isolated FastAPI harness (without the database/LLM application startup). Browser automation could not launch Chrome under the host sandbox, so the browser smoke script and real microphone/audio/RAG round trip still require a local run with the full backend services running.
