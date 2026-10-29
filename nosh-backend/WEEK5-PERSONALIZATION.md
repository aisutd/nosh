# NOSH Week 5: personalization and cooking memory

Implementation is in `/Users/thiru/Documents/NOSH/voice_agent/nosh-backend`.
This guide is in the chat workspace because the resumed session no longer has write access to that repository.

## What is implemented

- Profile UI: explicit cooking confidence, instruction detail, dietary preferences, ingredients to avoid and skills that need support.
- Cooking UI: save a session outcome, recipe rating, difficulty and free-text feedback. Available on standard recipe pages, selected/saved RAG recipes, and recipes generated in the voice assistant.
- Profile history: review up to 30 recent sessions and reset cooking preferences/history.
- Authenticated persistence: preferences and feedback are stored on the existing MongoDB user document. Account identity comes from the verified login token, never from a supplied user ID. Guests retain ordinary cooking access without persistent memory. Invalid supplied tokens fail authentication.
- Future recommendations: preference signals and recent recipe ratings re-rank pantry-matched retrieval candidates. This is a soft ranking, not a hard dietary filter or safety classifier.
- Future instructions: saved skill level, guidance preference, difficulties and the latest eight session summaries are added to the generation prompt and recipe Q&A context as untrusted data. Source recipe quantities, ingredients, times and step order remain governed by the existing recipe rules and judge.
- Memory is explicit user feedback, not model retraining. The system does not silently infer a higher skill level or store complete microphone recordings/transcripts. Users update their confidence as they grow.

## Files and endpoints

- `Backend/personalization.py`: bounded schemas, allowlisted memory context, prompt rules, recommendation ranking.
- `Backend/routes/memory.py`: authenticated memory CRUD.
- `Backend/security.py`: optional authentication for public cooking endpoints; supplied invalid tokens are rejected.
- `Backend/nosh_pipeline.py`, `Backend/llm/nosh_generation.py`, `Backend/llm/recipe_chat.py`: ranking and prompt integration.
- Recipe and voice routes load personalization server-side from the authenticated account. The frontend sends the existing bearer token with recipe searches and voice turns.
- `Frontend/src/components/CookingMemory.jsx` and its stylesheet: profile preferences/history and cooking feedback.
- `Frontend/src/pages/Profile.jsx`: profile integration. `VoiceAgent.jsx`: feedback on cooking sessions.
- `GET /memory`, `PUT /memory/preferences`, `POST /memory/sessions`, `DELETE /memory`.

Existing accounts need no migration: missing memory fields return defaults; fields are saved on first use. Preferences are per account. History appends use MongoDB's atomic `$push` with `$slice: -30`.

## Verified on October 28, 2026

- Production frontend build: passed.
- Lint for changed components, pages and API helper: passed.
- All 15 backend tests: passed, including six ingredient-parser regressions, five voice tests and four personalization tests.
- Multi-session simulation: three consecutive cooking sessions receive increasing prior-session context; fresh HTTP clients see stored history; accounts remain isolated; explicit skill updates persist; memory reset works.
- Authentication, invalid input, 30-session retention, eight-session prompt limit, recommendation ordering and actual LLM prompt construction are covered.
- Browser checks before the interruption confirmed the profile UI and saving dietary preferences and cooking difficulties through the real memory routes with an isolated database fixture.

Tests use a fake MongoDB collection and LLM responses. They verify application behavior and prompt context, not live model answer quality or a connection to the team's MongoDB instance.

## Remaining local acceptance check

The resumed environment blocks local server binding and repository writes. The cooking-feedback browser round trip could not be completed after the interruption. Run the normal backend with the team's MongoDB, Ollama models and recipe index, then the frontend:

1. Log in and open Profile. Save a skill level, dietary preference and a difficulty.
2. Search for a recipe, cook it, and submit “How did cooking go?” feedback.
3. Return to Profile and confirm that the session appears; reload and confirm it remains.
4. Start another cooking session and ask for help with the earlier difficulty. Check that the explanation fits the saved skill/detail preference while preserving source recipe facts.
5. Change the preference and repeat. Sign in with a different account and confirm no history is shared.
6. Use the reset UI and confirm defaults and empty history return.

An isolated UI fixture is provided at `Backend/tests/memory_ui_fixture.py`. It has fixture-only login and fake data, disappears on exit, and is never imported by `main.py`. Do not run it as the production backend. It can be used to verify profile/feedback UI without MongoDB or model calls, but cannot validate live personalized generation.

Backend tests, from `Backend`, with the project's dependencies installed:

```sh
python -m unittest discover -s tests -v
```

Frontend checks, from `Frontend`:

```sh
npm run build
npx eslint src/components/CookingMemory.jsx src/components/VoiceAgent.jsx src/components/GenerateRecipe.jsx src/pages/Profile.jsx src/pages/RagCook.jsx src/pages/Cook.jsx src/lib/api.js
```

Earlier Week 4 changes and the user's existing model/requirements edits remain in the working tree. No commit, push, deployment or production data mutation was performed.
