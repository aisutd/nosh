# App consolidation

The earlier integration placed voice and memory in a second app at nosh-backend/.
Mock_Main gained newer inventory, substitutions and servings in the root app.
Running either copy meant missing the other copy's features.

The root Backend/ and Frontend/ are now authoritative; the nested app is removed.
Current root retrieval, availability, source adaptation, scaling, saved-pantry
checks, inventory routes and UI were retained. Voice and authenticated memory
routes, profile controls and real pantry/cooking voice controls were integrated.
Serving changes reset the voice session to the returned recipe. Signed-in voice
generation uses the current server-side pantry.

Personalization ranks eligible recommendations and is supplied to LLM instruction
generation, repair and Q&A. Deterministic source-preserving instructions remain
source-preserving instead of being rewritten just for style.

After pulling: stop old servers; follow the README root-folder commands; configure
Backend/.env; run npm ci in Frontend; verify GET /health lists voice and inventory.
Use Chrome for speech recognition. No secrets, database, weights or vector index
were copied or migrated. Existing external checkouts are not auto-updated.
Cross-message conversations and fraction pronunciation remain separate follow-ups.

Legacy root tests now use the shared staple policy and catalog-backed substitutions,
provide current recipe metadata, and explicitly exercise the LLM branch when
testing generation/judge behavior. Root CLI calls delegate to the same backend
pipeline, so tests no longer target a separate, older RAG implementation.

Verification: 83 Backend tests, 75 root/RAG tests, five frontend API tests,
production frontend build and full frontend source lint pass. A real FastAPI
TestClient checks that one application exposes voice, memory and inventory;
selected generation receives both servings and personalization; authenticated
voice requests use current server-side pantry ingredients. No microphone or
real database mutation was performed during these consolidation checks.

Docker compose files remain starter placeholders and are not application launch
commands. Use README's two-terminal instructions for this app.
