import re
from collections import Counter
from pathlib import Path

import cv2
import easyocr
import numpy as np
import pandas as pd

from retrieval.ingredients import normalize_name, required_ingredients, PANTRY

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "cleaned_recipes.csv"
_reader = None                                   # OCR model, loaded on first use
_vocab = None                                    # ingredient names, built on first use


def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader

_JUNK_START = {"and", "or", "at", "for", "with", "container"} 
# Build the ingredient vocabulary from the recipes (once)
def get_vocab():
    global _vocab
    if _vocab is None:
        counts = Counter()
        for raw in pd.read_csv(CSV_PATH)["ingredients"].dropna():
            counts.update(required_ingredients(raw) or ())
        # keep names used in at least 5 recipes, skip salt/water/etc. and very short words
        _vocab = {n for n, c in counts.items()
            if c >= 2 and n not in PANTRY and len(n) >= 3
            and n.split()[0] not in _JUNK_START}
        _vocab |= {
            "milk", "egg", "butter", "cheese", "yogurt", "cream", "bread", "rice", "pasta",
            "chicken", "beef", "pork", "bacon", "ham", "turkey", "salmon", "tuna", "shrimp",
            "tomato", "potato", "onion", "garlic", "carrot", "celery", "spinach", "lettuce",
            "broccoli", "mushroom", "cucumber", "zucchini", "cabbage", "corn", "bean",
            "apple", "banana", "orange", "lemon", "lime", "strawberry", "blueberry", "avocado",
            "flour", "sugar", "oil", "tortilla", "tofu", "ginger", "basil", "cilantro",
        }
    return _vocab

# Check every 1, 2 and 3 word phrase in the OCR text against the vocabulary
def match_ingredients(texts):
    vocab = get_vocab()
    words = re.findall(r"[a-z]+", " ".join(texts).lower())
    found = set()
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            name = normalize_name(" ".join(words[i:i + n]))   # "whole milk" -> "milk"
            if name in vocab:
                found.add(name)
    return sorted(found)


# Takes raw image bytes, returns [{"name": "milk", "confidence": 0.82}] (same shape as YOLO)
def detect_text_ingredients(data: bytes) -> list[dict]:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not read image")

    h, w = img.shape[:2]
    scale = 1280 / max(h, w)
    if scale < 1:                                # shrink big photos
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=(255, 255, 255))

    results = get_reader().readtext(img)
    good = [(text, conf) for _, text, conf in results if conf > 0.4]   # confident lines only
    texts = [text for text, _ in good]

    found = []
    for name in match_ingredients(texts):
        confs = [c for t, c in good if name in t.lower()]
        found.append({"name": name, "confidence": round(max(confs, default=0), 4)})
    return found