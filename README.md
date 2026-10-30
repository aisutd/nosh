# NOSH
## Description
NOSH is an AI-powered student cooking assistant that turns ingredients from a refrigerator photo into practical, budget-friendly meals. It combines ingredient detection, recipe retrieval, and a hands-free voice interface for substitutions, timers, and step-by-step cooking guidance.
Planned Technologies

* Python and JavaScript/TypeScript
* React and Tailwind CSS
* FastAPI or Flask with MongoDB and Redis
* YOLOv8, OpenCV, LangChain, RAG, vector search, speech-to-text, and text-to-speech

Docker Setup
Make sure Docker Desktop is installed and running.

```
docker compose up -d
docker compose down
docker compose ps
```

This is a generic starter configuration. The team can add project-specific dependencies and startup commands later.

---

## Project folders
- `Backend/`  FastAPI + MongoDB API
- `Frontend/` React web app (Vite)
- `Mobile/`   Expo app (shows the web app + native camera)
- `Docker Folder/` Docker files (not yet updated for this layout; run `docker compose` from inside this folder)

## Run the backend
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r Backend\requirements.txt
cd Backend
copy .env.example .env     # then fill in your values
uvicorn main:app --reload --host 0.0.0.0
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 # for mobile
```
API docs: http://localhost:8000/docs

### Secret key
`SECRET_KEY` signs the login tokens. Generate your own with:
```
python -c "import secrets; print(secrets.token_hex(32))"
```
Copy the output into `Backend/.env` as `SECRET_KEY=...`.
`MONGO_URI` must come from the team (ask privately, it contains the database password).

## Run the web app
```
cd Frontend
npm install
npm run dev -- --host
```
Open http://localhost:5173

## Run the phone app
```
cd Mobile
npm install
npx expo start
```
Scan the QR code with Expo Go (SDK 57). Phone and laptop must be on the same Wi-Fi.
Edit the IP address in `Mobile/App.js` and the CORS list in `Backend/main.py` to match your laptop (`ipconfig`).

## Adding an endpoint
1. Make a file in `Backend/routes/` with `router = APIRouter()` and a function like `@router.post("/name")`.
2. Register it in `Backend/main.py`: `app.include_router(yourfile.router)`.
3. Test it at http://localhost:8000/docs

`/scan` takes an image (field name `image`) and returns `{"ingredients": [...]}`. It needs a login token.

## Rules
- Never commit `.env`.

## YOLO and hybrid RAG integration (macOS/Linux)

The image and JSON recipe endpoints live in `Backend/routes/pipeline.py`.
From the repository root, use the existing virtual environment:

```bash
source .venv/bin/activate
python -m pip install -r Backend/requirements.txt
cd Backend
python -m rag.build_embeddings  # first setup only
python -m uvicorn main:app --reload --port 8000
```

Put your private configuration in `Backend/.env` (see `.env.example`), including
`MONGO_URI` and a private `SECRET_KEY` for authentication. Put the trained weights
in `Backend/models/best.pt`. Neither file belongs in Git. Ollama must be running
with `llama3.2` and `gemma2` available for generation.

- `POST /recipes/from-image`: multipart `image` and optional `user_query`.
- `POST /recipes/from-detections`: JSON `detections.ingredients` entries with
  `name` and `confidence`, plus optional `user_query`.
- Both return `detections`, normalized `ingredients`, and the pipeline `result`.
  `no_recipes_found` is a valid result when no source satisfies ingredient constraints.

The current frontend still calls OCR `/scan` and MongoDB `/recipes/find`.
These are preserved; frontend integration with the YOLO/RAG routes is pending.

## Pantry substitutions

The active frontend uses `/recipes/options` and `/recipes/generate-selected`;
the earlier note that frontend RAG integration is pending is outdated.

`Backend/data/substitutions.json` holds 28 alternatives for 24 ingredient types,
with structured component amounts, limitations and source references.
`Backend/retrieval/substitutions.py` validates and loads this versioned catalog.
The catalog is local JSON, not a live MongoDB collection; no credentials or network
are needed to use it. Restart the backend after editing the catalog.
Both retrieval engines and selected/saved recipe generation require every
replacement component to be present in the reviewed pantry. Matching uses explicit
normalization/aliases, not embedding guesses; quantity sufficiency is not tracked.
Only one-hop replacements are supported. Plain yogurt must be listed explicitly.

Recipe options include a `substitutions` array and show it on the swipe cards.
Approved generation returns the applied array alongside the existing recipe text;
Changes and Steps describe the adaptation. The judge checks recipe suitability,
ratios and constraints; unsupported adaptations still fail validation. Candidate
options are suggestions until generation is validated. Saved recipes recompute
substitutions from their saved pantry context. No database migration is needed.

Run offline regression tests from Backend: `../.venv/bin/python -m unittest discover -s tests -v`.

### Expanded chart-based coverage

The catalog includes dairy, butter, flour variants, leavening, thickeners, broth,
spice blends, garlic, honey, mustard and dressing substitutions. Ratios are
adapted from [Colorado State University Extension](https://extension.colostate.edu/resource/ingredient-substitutions/).
Each entry keeps source quantity/unit, replacement component quantity/unit,
preparation, limitations and attribution. Units such as tablespoon juice refer to
the component preparation, not a count of whole lemons.

Recipe-context gates apply to baking cream, thickeners, garlic powder, and
mayonnaise replacements in both search engines and selected-recipe validation.
These conservative keyword checks can exclude suitable recipes; the LLM judge
still checks suitability. Ingredients whose replacements need complex recipe-wide
adjustments (such as many egg, sugar and baking-soda swaps) are deliberately not
added automatically. This catalog does not certify dietary or allergy safety.

To test: compare an exact recipe pantry with the same pantry missing milk but
containing evaporated milk, or missing butter but containing baking margarine.
Search again after each change. Cream requiring whipping must not receive the
milk-and-butter baking replacement. Generated instructions remain subject to the
existing validation; expanded coverage does not resolve local-model reliability.
