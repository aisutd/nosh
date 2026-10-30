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

