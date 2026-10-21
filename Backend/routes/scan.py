"""Authenticated refrigerator image scanning with the trained YOLO model."""
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from fastapi.concurrency import run_in_threadpool
from security import get_current_user
from vision.detector import detect_ingredients

router = APIRouter()
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/scan")
async def scan(image: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Return pantry-compatible names and the original YOLO detections."""
    try:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")
        data = await image.read(MAX_IMAGE_BYTES + 1)
    finally:
        await image.close()

    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    try:
        detections = await run_in_threadpool(detect_ingredients, data)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="The ingredient detection model is unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ingredients = sorted({
        item["name"].replace("_", " ").strip().lower()
        for item in detections["ingredients"]
        if item["name"].replace("_", " ").strip()
    })
    return {"ingredients": ingredients, "detections": detections}
