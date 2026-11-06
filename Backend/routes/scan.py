"""Authenticated refrigerator image scanning with the trained YOLO model."""
import logging
from urllib.error import URLError

from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from fastapi.concurrency import run_in_threadpool
from security import get_current_user
from vision.detector import detect_ingredients
from vision.ocr import detect_text_ingredients
from database.configurations import inventory
from retrieval.ingredients import normalize_name
from vision.video_detector import detect_video_ingredients
import os
import tempfile

router = APIRouter()
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB


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

    warnings = []
    try:
        ocr_found = await run_in_threadpool(detect_text_ingredients, data)   # OCR on the same photo
    except (ValueError, URLError, OSError) as exc:
        # Text recognition is optional; retain successful object detections.
        logging.getLogger(__name__).warning("OCR unavailable; returning YOLO detections: %s", exc)
        warnings.append("Text recognition is unavailable. Object detections are still included.")
        ocr_found = []
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
    return {"ingredients": ingredients, "detections": detections, "warnings": warnings}

@router.post("/scan-video")
async def scan_video(
    video: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="File must be a video")

    try:
        data = await video.read(MAX_VIDEO_BYTES + 1)
    finally:
        await video.close()

    if len(data) > MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="Video must be 50 MB or smaller.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded video is empty.")

    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_video:
            temp_video.write(data)
            temp_path = temp_video.name

        # The detector expects a file path, so pass it the temporary video file.
        video_result = await run_in_threadpool(
            detect_video_ingredients,
            temp_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="The video detection model is unavailable.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    quantity_estimates = {}

    for raw_name, estimate in video_result.get("quantity_estimates", {}).items():
        if not isinstance(estimate, dict) or estimate.get("quantity") is None:
            continue

        name = normalize_name(raw_name.replace("_", " "))
        quantity = int(estimate["quantity"])

        quantity_estimates[name] = {
            "quantity": quantity,
            "unit": "count",
        }

        # Replace the inventory amount with the latest video scan estimate.
        await inventory.update_one(
            {"user_id": current_user["_id"], "name": name},
            {"$set": {"quantity": quantity, "unit": "count"}},
            upsert=True,
        )

    ingredients = sorted(quantity_estimates)

    return {
        "ingredients": ingredients,
        "quantity_estimates": quantity_estimates,
        "ingredient_summary": video_result.get("ingredient_summary", []),
        "detections": video_result,
    }
