# Week 6: frontend reliability and presentation polish

The running application is in this repository's Backend and Frontend folders.
Cross-message conversation and natural fraction pronunciation remain queued for after Week 6.

## Changes

- Unified pantry, recipe, profile and voice panels with the existing warm dark/orange palette. Removed the pale green panels, low-contrast conversation text and oversized checkbox styling conflicts.
- Added a constrained desktop layout, phone layout, visible keyboard focus, reduced-motion support and accessible input/removal labels.
- Replaced placeholder/slang copy with straightforward cooking language. Voice controls use consistent icons.
- Recipe recommendations now have a direct “Cook this recipe” link. Users can still swipe, skip and save.
- Saved recipes have keyboard-accessible cooking links, explicit loading/error/empty states, and guarded removal errors.
- Approved recipe instructions appear as a numbered method. Source wording and quantities are preserved. Speech pronunciation has not changed.
- Session feedback is expandable so it does not overwhelm the cooking view.
- Consolidated API URL configuration and request handling. Requests now have cancellation and timeouts; HTTP and validation failures provide actionable messages.
- Login recovery distinguishes expired tokens from transient server failure. A server outage no longer discards the stored token.
- Pantry add/remove and scan failures are visible. Concurrent pantry actions are guarded, scan errors release the busy state, and late account-specific responses cannot repopulate a logged-out pantry.
- Added a not-found page and clearer Chrome guidance for speech-recognition network failures.

## Run

Backend, in one terminal:

```sh
cd /Users/thiru/Documents/NOSH/voice_agent/nosh-backend
source /Users/thiru/Documents/NOSH/.venv/bin/activate
cd Backend
python -m uvicorn main:app --reload --port 8000
```

Frontend, in another terminal:

```sh
cd /Users/thiru/Documents/NOSH/voice_agent/nosh-backend/Frontend
npm run dev
```

Use Google Chrome and open http://localhost:5173. Keep the backend, configured MongoDB and Ollama available. A different backend can be configured with VITE_API_URL before starting or building the frontend.

## Five-minute team demo

Before presenting: allow Chrome microphone access, verify the account login and Ollama models, and open an already validated recipe. Initial model/index loading and generation can take minutes; avoid relying on a cold start during a short presentation.

1. Pantry: explain that manual ingredients and fridge photos feed the same pantry. The known lemonade example uses lemon and sugar; source water is handled by the existing pipeline. Avoid changing someone's real pantry solely for a demo without their agreement.
2. Recommendations: select Find Recipes. Point out the recipe source and Cook this recipe action. Save the recipe if demonstrating persistence.
3. Cooking: show the readable method and source link. Use Start cooking, Next step and Repeat. In Chrome, try one spoken command and a current-recipe cooking question.
4. Profile: show saved confidence, detail preferences and difficulties. Users choose their own level; the system does not silently promote them.
5. Feedback: expand How did cooking go? Explain how saved outcomes and difficulties inform later instructions. Save only genuine feedback or use the isolated test fixture for simulated sessions.

Do not present dietary preferences as a verified allergy filter. Do not promise cross-turn topic switching or natural fraction speech yet. The in-app browser has previously failed browser speech recognition; use Chrome for the voice demo.

## Checks

From Frontend:

```sh
npm run build
npm run lint
node --test tests/api.test.cjs
```

From Backend, in the configured Python environment:

```sh
python -m unittest discover -s tests
```

The five new API tests exercise HTTP status preservation, friendly network errors, timeout/retry, page cancellation and authenticated memory validation. Existing backend tests cover ingredients, voice routing and multi-session personalization. Test doubles remain in tests only.

No deployment or push is part of this Week 6 change. The original repo still contains earlier Week 4/5 work and user edits; the separate publish-nosh checkout is not automatically synchronized with these new changes.

## Verification results

- Frontend production build and full source lint: passed.
- Five frontend API regression tests: passed.
- All 15 existing backend tests: passed using the configured NOSH virtual environment.
- Live browser: existing signed-in pantry loaded; saved recipe opened, generated and validated instructions; Start cooking returned the expected first step; feedback form expanded; Profile preferences and history loaded. No invented feedback or preferences were saved.
- Pantry and cooking pages: 390px viewport had no horizontal overflow. Desktop layout was visually inspected.
- Photo scanning and native mobile camera were not re-run; frontend scan failure recovery was improved. Chrome microphone recognition was verified by the user before Week 6; the revised controls retain that speech path.
- Snapshot: `/Users/thiru/Documents/ChatGPT/NOSH/week6-cooking.jpg`.
