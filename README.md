# NOSH

## One app, one launch path

Use the repository-root **Backend/** and **Frontend/**. Voice, memory,
personalization, inventory, substitutions, and serving controls run together there.
The old nested `nosh-backend/` app has been consolidated and removed. Stop old
backend and Vite processes before starting this checkout.

## Description

NOSH is an AI-powered student cooking assistant that turns ingredients from a
refrigerator photo or video into practical, budget-friendly meals. It combines
ingredient detection, recipe retrieval, and a voice interface for cooking
questions, substitutions, and step-by-step guidance.

Technologies include:

- Python and JavaScript
- React and Vite
- Three.js, React Three Fiber, and Drei
- FastAPI and MongoDB
- YOLO, OpenCV, and EasyOCR
- Hybrid RAG and vector search
- Speech-to-text and text-to-speech

## Project folders

- `Backend/` — FastAPI and MongoDB API
- `Frontend/` — React web app and interactive presentation
- `Mobile/` — Expo app showing the web app with native camera, microphone, and speech playback
- `Docker Folder/` — Docker files; not yet updated for this layout

## Setup

Run these commands from the repository root.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r Backend/requirements.txt
Copy-Item Backend/.env.example Backend/.env
```

### macOS / Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r Backend/requirements.txt
cp Backend/.env.example Backend/.env
```

Fill in `Backend/.env` with your own configuration. If it already exists,
skip the copy command to keep your existing configuration.

MongoDB and `SECRET_KEY` must be configured before running the app.

### Secret key

`SECRET_KEY` signs the login tokens. Generate your own with:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Copy the output into `Backend/.env` as `SECRET_KEY=...`.

Get the `MONGO_URI` connection string privately from the team. It contains
database credentials.

## Set up RAG and run the backend

Before starting:

- Fill in `Backend/.env`.
- Put the trained model weights at the path configured by `MODEL_PATH`.
  The video detector currently references `Backend/models/best (1).pt`.
- Start Ollama with the models required by the backend configuration.

From the repository root, with your virtual environment activated:

```sh
cd Backend
python -m rag.build_embeddings
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Build the recipe index on first setup or when the recipe data changes.
For later launches, skip `python -m rag.build_embeddings`.

API docs: http://localhost:8000/docs

Health check: http://localhost:8000/health

The health check should list `recipes`, `inventory`, `voice`, and `memory`.

## Run the web app

In a second terminal, from the repository root:

```sh
cd Frontend
npm ci
npm run dev -- --host
```

Open http://localhost:5173 in **Google Chrome**.

Vite uses port 5173 strictly so a second accidental launch fails instead of
silently opening another app on 5174.

`VITE_API_URL` can override the backend address. Restart Vite after changing it.

## Presentation demo

NOSH includes an interactive presentation with a live app displayed inside an
animated 3D phone built with Three.js, React Three Fiber, and Drei.

After starting the web app, open:

http://localhost:5173/presentation

Keep the backend running to use scanning, recipe generation, inventory, and voice.

### Guided walkthrough

Open **Preparation → Open live phone** to sign in before presenting. Use
**Check / Retry readiness** to check backend reachability and sign-in. The health
endpoint alone does not verify MongoDB, model files, or Ollama. Prepare a scan
photo/video and test microphone permissions before the talk.

1. Begin the presentation and press **→** to introduce the problem.
2. Open **Scan fridge** in the phone. Press → to explain training and video tracking.
3. Scan ingredients, tap **Find Recipes**, and review substitutions. Press **→** to explain them.
4. **Save** a recipe, open **Saved**, and select it.
5. Adjust **Servings**, open **Steps**, and use a voice control or send a question.
6. Mark the recipe cooked, then open **My inventory**. Only opening the inventory
   screen reveals its presentation explanation.
7. Press → for team challenges, future work, and the thank-you screen.

**← / →** navigate explanations. At action checkpoints, →
shows what to do in the phone instead of skipping ahead. Click outside the phone
and controls before using arrow keys. Press **End** to jump to the wrap-up if you need to finish early.

**Use sample demo** starts a separate, clearly labeled tomato-pasta walkthrough.
Its scanning and voice replies are simulated; it makes no backend requests and
never changes your account or real inventory. **Reset sample** clears sample
state only. **Return to live app** restores the still-mounted live phone; any
live voice conversation is paused when switching to samples. **Reset presentation**
resets the talk without clearing the live app.

### Presentation checks

With Vite running, run `node Frontend/tests/presentation-smoke.cjs` from the repo
root with `NODE_PATH` pointing to a Playwright installation and Chrome installed.
The test uses isolated API fixtures, not a real account, and covers the live UI
walkthrough, retry states, sample isolation/reset, inventory gating, keyboard
navigation, and desktop/mobile layouts.

### Dependencies

The presentation dependencies are included in `Frontend/package.json` and
installed by `npm ci`.

When changing dependencies, commit both `Frontend/package.json` and
`Frontend/package-lock.json`. Do not commit `node_modules/`.

## Run the phone app

In another terminal, from the repository root:

```sh
cd Mobile
npm ci
npx expo start
```

Scan the QR code with a compatible version of Expo Go. Phone and laptop must be
on the same Wi-Fi, and the backend and frontend must both be running.

Update the addresses in `Mobile/App.js` to match your laptop's local IP address.
On Windows, use `ipconfig` to find it. Make sure the frontend origin is allowed
by the CORS configuration in `Backend/main.py`.

### Voice on web and mobile

- The website uses browser speech recognition to turn speech into text.
- The Expo app records audio and sends it to `POST /voice/transcribe`.
- Both send the resulting text and cooking context to `POST /voice/turn`.
- Web replies use browser text-to-speech; mobile replies use native speech playback.

Browser microphone access requires HTTPS or localhost. Opening the website over
a plain HTTP LAN address on a phone may disable browser microphone access.

Mobile transcription requires `DEEPGRAM_API_KEY` in `Backend/.env`.

Voice uses the same signed-in user and current pantry as the rest of the app.
Do not run the desktop voice script for the web or Expo app.

Desktop users may still run `voice-agent/voice_agent.py`.

## Recipe endpoints

The image and JSON recipe endpoints live in `Backend/routes/pipeline.py`:

- `POST /recipes/from-image`: multipart `image` and optional `user_query`.
- `POST /recipes/from-detections`: JSON `detections.ingredients` entries with
  `name` and `confidence`, plus optional `user_query`.
- Both return `detections`, normalized `ingredients`, and the pipeline `result`.
- `no_recipes_found` is a valid result when no source satisfies ingredient constraints.

The root `nosh_pipeline.py` is a compatibility entry point delegating to
`Backend/nosh_pipeline.py`.

Root `requirements.txt` is for evaluation tooling;
`Backend/requirements.txt` is for the web application.

## Scanning endpoints

Scanning requires a login token.

- `POST /scan`: upload an image using the multipart field `image`.
- `POST /scan-video`: upload a video using the multipart field `video`.

The scan results include detected ingredient names. Video scanning also produces
tracking-based quantity estimates.

## Docker setup

The Docker files have not yet been updated for the current layout. Use the
manual setup above for now.

For work on the existing Docker configuration, run these commands from
`Docker Folder/`:

```sh
docker compose up -d
docker compose down
docker compose ps
```

## Adding an endpoint

1. Make a file in `Backend/routes/` with `router = APIRouter()` and a function
   such as `@router.post("/name")`.
2. Register it in `Backend/main.py`: `app.include_router(yourfile.router)`.
3. Test it at http://localhost:8000/docs.

## Rules

- Never commit `.env` files or API keys.
- Keep private model weights and generated scan outputs out of commits.
- Commit dependency manifests and lockfiles when dependencies change.
- Do not commit virtual environments or `node_modules/`.