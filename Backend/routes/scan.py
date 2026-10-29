"""Authenticated refrigerator image scanning with the trained YOLO model."""
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from fastapi.concurrency import run_in_threadpool
from security import get_current_user
from vision.detector import detect_ingredients
from vision.ocr import detect_text_ingredients
from database.configurations import inventory
from retrieval.ingredients import normalize_name

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

    try:
        ocr_found = await run_in_threadpool(detect_text_ingredients, data)   # OCR on the same photo
    except ValueError:
        ocr_found = []                              # OCR couldn't read it, YOLO results still count
    detections["ingredients"] += ocr_found          # add OCR results to YOLO's list

    ingredients = sorted({
        item["name"].replace("_", " ").strip().lower()
        for item in detections["ingredients"]
        if item["name"].replace("_", " ").strip()
    })
    for name in ingredients:                      # list of names YOLO found
        await inventory.update_one(
            {"user_id": current_user["_id"], "name": normalize_name(name)},
            {"$setOnInsert": {"quantity": 1, "unit": "count"}},   # only set if it's new
            upsert=True,
        )
    return {"ingredients": ingredients, "detections": detections}