from io import BytesIO
from pathlib import Path
from threading import Lock

from PIL import Image, UnidentifiedImageError
from ultralytics import YOLO


# Resolve the model location relative to this file.
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "best.pt"

_model = None
_model_lock = Lock()


def detect_ingredients(image_bytes: bytes) -> dict:
    """Run YOLO on an uploaded image and return ingredient detections."""
    global _model

    if not image_bytes:
        raise ValueError("The uploaded image is empty.")

    try:
        with Image.open(BytesIO(image_bytes)) as uploaded_image:
            image = uploaded_image.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The uploaded file could not be read as an image.") from exc

    # Load once and prevent simultaneous requests from sharing model execution.
    with _model_lock:
        if _model is None:
            if not MODEL_PATH.is_file():
                raise FileNotFoundError(f"YOLO model not found: {MODEL_PATH}")

            _model = YOLO(str(MODEL_PATH))

        results = _model.predict(
            source=image,
            conf=0.25,
            verbose=False,
        )

        ingredients = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls.item())
                confidence = float(box.conf.item())
                name = result.names[class_id]

                ingredients.append({
                    "name": name,
                    "confidence": round(confidence, 4),
                })

    return {"ingredients": ingredients}