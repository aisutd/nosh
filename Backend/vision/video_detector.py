from ultralytics import YOLO  # Import the YOLO model from the Ultralytics library
from pathlib import Path  # Handle file paths
import cv2  # Read video files
from collections import Counter, defaultdict
from uuid import uuid4  # Give each scan its own output folder


# File paths
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR.parent / "models" / "best (1).pt"
MODEL = None  # Load the model once, then reuse it


def detect_video_ingredients(video_path: str) -> dict:
    """Track ingredients in an uploaded video and return the results."""
    global MODEL

    VIDEO_PATH = Path(video_path)

    if not VIDEO_PATH.exists():
        raise FileNotFoundError(f"Video not found: {VIDEO_PATH}")

    # Create a separate folder for this scan so annotated videos don't overwrite each other.
    run_dir = BASE_DIR / "scan_outputs" / uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=True)

    # Get the video FPS (frames per second) and total frame count.
    cap = cv2.VideoCapture(str(VIDEO_PATH))

    if not cap.isOpened():
        raise ValueError("Could not open the video.")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    if fps <= 0:
        raise ValueError("Could not read a valid FPS from the video.")

    print(f"Video FPS: {fps}")
    print(f"Total frames: {total_frames}")

    # Load the trained model the first time this function is called.
    if MODEL is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"YOLO model not found: {MODEL_PATH}")
        MODEL = YOLO(str(MODEL_PATH))

    model = MODEL
    print(model.names)

    results = model.track(
        source=str(VIDEO_PATH),
        tracker="bytetrack.yaml",
        stream=True,  # Stream video frames to the model
        persist=True,  # Keep tracking IDs between frames
        save=True,  # Save the annotated video
        project=str(run_dir),
        name="annotated_test_result",
        verbose=False,
    )

    ingredients = []  # Store detections and their confidence scores

    # Extract ingredient names, confidence scores, track IDs, timestamps, and boxes.
    for frame_number, result in enumerate(results):
        timestamp = frame_number / fps

        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            name = result.names[class_id]

            track_id = None  # Some detections may not receive a tracking ID
            if box.id is not None:
                track_id = int(box.id[0])

            # Get the bounding box coordinates: [x1, y1, x2, y2]
            box_coordinates = box.xyxy[0].tolist()
            box_coordinates = [round(coord, 2) for coord in box_coordinates]

            ingredients.append({
                "name": name,
                "confidence": round(confidence, 4),
                "track_id": track_id,
                "frame_number": frame_number,
                "timestamp": round(timestamp, 3),
                "box": box_coordinates,
            })

    print("Total detections:", len(ingredients))

    # Count each tracked object once.
    frames_by_track = defaultdict(lambda: defaultdict(set))
    untracked_by_class = Counter()
    class_names = dict.fromkeys(
        detection["name"] for detection in ingredients
    )

    for detection in ingredients:
        name = detection["name"]
        track_id = detection["track_id"]

        if track_id is None:
            # Missing IDs cannot be deduplicated, so report these without counting them.
            untracked_by_class[name] += 1
            continue

        frames_by_track[name][track_id].add(detection["frame_number"])

    # Calculate quantity estimates for each ingredient class.
    quantity_estimates = {}

    for name in class_names:
        tracks = frames_by_track[name]
        quantity = len(tracks)

        quantity_estimates[name] = {
            "quantity": quantity,
            "unit": "objects",
            "method": "persistent_unique_track_ids",
            "untracked_detections": untracked_by_class[name],
        }

    # Add the final class count to each frame-level detection.
    for detection in ingredients:
        detection["class_quantity"] = quantity_estimates[
            detection["name"]
        ]["quantity"]

    # Group detections by ingredient and track ID to calculate average confidence.
    track_confidences = defaultdict(lambda: defaultdict(list))

    for detection in ingredients:
        name = detection["name"]
        track_id = detection["track_id"]

        if track_id is not None:
            track_confidences[name][track_id].append(
                detection["confidence"]
            )

    # Create a simpler summary for the frontend.
    ingredient_summary = []

    for name in class_names:
        counted_track_confidences = []

        for track_id, confidences in track_confidences[name].items():
            average_confidence = sum(confidences) / len(confidences)
            counted_track_confidences.append(average_confidence)

        average_confidence = (
            sum(counted_track_confidences) / len(counted_track_confidences)
            if counted_track_confidences
            else None
        )

        ingredient_summary.append({
            "name": name,
            "count": len(counted_track_confidences),
            "confidence": (
                round(average_confidence, 4)
                if average_confidence is not None
                else None
            ),
        })

    # Ultralytics saves the annotated video in this folder.
    annotated_video_path = (
        run_dir / "annotated_test_result" / VIDEO_PATH.name
    )

    # Return the results to the API; no JSON files are written.
    return {
        "ingredients": sorted(class_names),
        "detections": ingredients,
        "quantity_estimates": quantity_estimates,
        "ingredient_summary": ingredient_summary,
        "output_folder": str(run_dir),
        "annotated_video": str(annotated_video_path),
        "fps": fps,
        "total_frames": total_frames,
    }
