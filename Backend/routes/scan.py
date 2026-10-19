import re
import cv2                                  
import easyocr                             
import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from fastapi.concurrency import run_in_threadpool   # runs slow code without freezing the server
from security import get_current_user

router = APIRouter()

# Scan Endpoint
# temporary vocabulary - replace with ingredient names from the database
VOCAB = {"milk", "egg", "butter", "cheese", "flour", "sugar", "beef", "tortillas"}
_reader = None                              # the OCR model, empty until first use


def get_reader():
    # load the OCR model once, on first use (loading is slow)
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)   # English only, CPU only
    return _reader


# Checks which ingredient words appear in the text found in the photo
def match_ingredients(texts, vocab):
    joined = " ".join(texts).lower()        # all the text as one lowercase string
    found = []
    for word in sorted(vocab, key=len, reverse=True):   # longest words first
        # \b = whole word only ("egg" won't match "eggplant"), s? allows plurals ("eggs")
        if re.search(rf"\b{re.escape(word)}s?\b", joined):
            found.append(word)
    return found


# Takes the raw image bytes and returns the ingredients found
def scan_image(data: bytes):
    # turn the bytes into an image OpenCV can use
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read image")

    # shrink big photos so the longest side is 1280px (faster, and avoids the resize error)
    h, w = img.shape[:2]
    scale = 1280 / max(h, w)
    if scale < 1:                           # only shrink, never enlarge
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    # add a 20px white border so text near the edge isn't cut off
    img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=(255, 255, 255))

    results = get_reader().readtext(img)    # each result is (box, text, confidence)
    texts = [text for _, text, conf in results if conf > 0.4]   # keep only confident reads

    found = match_ingredients(texts, VOCAB)
    # Add YOLO results to `found` here
    return found

# POST /scan: upload a photo, get the ingredients back (login required)
@router.post("/scan")
async def scan(image: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    # the field name must be "image" (same as form.append("image", file) in App.jsx)
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = await image.read()               # read the uploaded file
    try:
        found = await run_in_threadpool(scan_image, data)   # OCR is slow, so run it off the main thread
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"ingredients": found}