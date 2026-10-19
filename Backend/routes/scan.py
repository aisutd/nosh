import re
import cv2
import easyocr
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from fastapi.concurrency import run_in_threadpool
from security import get_current_user

router = APIRouter()

# Scan Endpoint
# temporary vocabulary - replace with ingredient names from the database
VOCAB = {"milk", "egg", "butter", "cheese", "flour", "sugar", "beef", "tortillas"}
_reader = None


def get_reader():
    # load the OCR model once, on first use (loading is slow)
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def match_ingredients(texts, vocab):
    joined = " ".join(texts).lower()
    found = []
    for word in sorted(vocab, key=len, reverse=True):
        if re.search(rf"\b{re.escape(word)}s?\b", joined):
            found.append(word)
    return found


def scan_image(data: bytes):
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read image")

    h, w = img.shape[:2]
    scale = 1280 / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=(255, 255, 255))

    results = get_reader().readtext(img)
    texts = [text for _, text, conf in results if conf > 0.4]

    found = match_ingredients(texts, VOCAB)
    # Add YOLO results to `found` here
    return found


@router.post("/scan")
async def scan(image: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await image.read()
    try:
        found = await run_in_threadpool(scan_image, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ingredients": found}