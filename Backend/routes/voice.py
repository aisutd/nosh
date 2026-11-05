import os

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from security import get_current_user
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from cooking_session import CookingSession

router = APIRouter()

voice_sessions = {}

class VoiceSessionRequest(BaseModel):
    recipe_text: str = Field(min_length=1, max_length=20000)
    ingredients: list[str] = Field(default_factory=list)

class VoiceQuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.post("/voice/transcribe")
async def transcribe_voice(
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Speech recognition is not configured.")

    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must be 10 MB or smaller.")
    if not data:
        raise HTTPException(status_code=400, detail="The audio recording is empty.")

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.deepgram.com/v1/listen",
                params={"model": "nova-3", "smart_format": "true"},
                headers={
                    "Authorization": f"Token {api_key}",
                    "Content-Type": audio.content_type or "audio/mp4",
                },
                content=data,
            )
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Speech transcription failed.") from exc
    finally:
        await audio.close()

    transcript = (
        result.get("results", {})
        .get("channels", [{}])[0]
        .get("alternatives", [{}])[0]
        .get("transcript", "")
        .strip()
    )

    return {"transcript": transcript}

@router.post("/voice/session")
async def start_voice_session(
    request: VoiceSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    session = CookingSession()
    session.load_approved_recipe(request.recipe_text, request.ingredients)
    voice_sessions[str(current_user["_id"])] = session
    return {"status": "ok"}

@router.post("/voice/ask")
async def ask_voice_question(
    request: VoiceQuestionRequest,
    current_user: dict = Depends(get_current_user),
):
    session = voice_sessions.get(str(current_user["_id"]))
    if not session:
        raise HTTPException(status_code=409, detail="Start voice cooking first.")

    result = await run_in_threadpool(session.ask, request.question)
    return {
        "status": result.get("status"),
        "answer": result.get("answer") or result.get("message", ""),
    }