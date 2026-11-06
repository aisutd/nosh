from ultralytics import YOLO # import the yolo model from ultralytics library
import json # imports the json library to save the results in a json file
from pathlib import Path # imports the Path class from the pathlib library to handle file paths
import cv2 # imports OpenCV, allowing us to run inference on video files
from collections import Counter, defaultdict

# File Paths
BASE_DIR = Path(__file__).resolve().parent # finds the folder where the script is located

MODEL_PATH = BASE_DIR / "best.pt" # finds the path to the trained model file (best.pt) in the same folder as the script
VIDEO_PATH = BASE_DIR / "test_videos" / "samplevideo2.mp4" # finds the path to the test video in the test_videos folder located in the same folder as the script
INGREDIENTS_OUTPUT_PATH = BASE_DIR / "ingredients.json"
QUANTITY_ESTIMATES_OUTPUT_PATH = BASE_DIR / "quantity_estimates.json"
INGREDIENT_SUMMARY_OUTPUT_PATH = BASE_DIR / "ingredient_summary.json"

# Getting The Video FPS (frame per second)
cap = cv2.VideoCapture(str(VIDEO_PATH)) # opens the video file for reading
fps = cap.get(cv2.CAP_PROP_FPS) # gets the frames per second (FPS) of the video using OpenCV's VideoCapture class
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) # gets the number of frames in the video
cap.release() # releases the video file when finished

if fps <= 0:
    raise ValueError("Could not read a valid FPS from the video.")

print(f"Video FPS: {fps}")
print(f"Total frames: {total_frames}")

# Loading The Model
model = YOLO(str(MODEL_PATH)) # loads the trained YOLO model from the specified path (best.pt) using the ultralytics library and stores it in the variable "model"
print(model.names) # prints the names of the classes that the model can detect

results = model.track(
    source=str(VIDEO_PATH),
    tracker="bytetrack.yaml",
    stream=True, # streams the video frames to the model for processing
    persist=True, # keeps the model's state between frames, allowing it to track objects across multiple frames
    save=True, # saves the annotated video with the detected ingredients to a file
    name="annotated_test_result",
    verbose=False
) # runs the model on the specified test video and stores the results in the variable "results"

ingredients = [] # initializes an empty list to store the detected ingredients and their confidence scores

# Loop through the results and extract the detected ingredients and their confidence scores
for frame_number, result in enumerate(results):
    timestamp = frame_number / fps

    if result.boxes is None:
        continue
    
    for box in result.boxes:
        class_id = int(box.cls[0]) # gets the class ID of the detected ingredient from the box object
        confidence = float(box.conf[0]) # gets the confidence score of the detected ingredient from the box object
        name = result.names[class_id] # gets the name of the detected ingredient using the class ID and the names dictionary in the result object

        track_id = None # assumes that the detection doesn't have a tracking id yet
        
        if box.id is not None:
            track_id = int(box.id[0]) # gets the tracking id and converts it to an integer if there is a tracking id

        # gets the bounding box coordinates: [x1, y1, x2, y2]
        box_coordinates = box.xyxy[0].tolist()
        box_coordinates = [round(coord, 2) for coord in box_coordinates]
        
        # appends the detected ingredient, its confidence score, tracking id, timestamp, and bounding box coordinates to the ingredients list
        ingredients.append({
            "name": name,
            "confidence": round(confidence, 4),
            "track_id": track_id,
            "frame_number": frame_number,
            "timestamp": round(timestamp, 3),
            "box": box_coordinates
        })

print("Total Detections:", len(ingredients))

# Count a track once if it recurs with sufficient confidence across enough frames.
frames_by_track = defaultdict(lambda: defaultdict(set))
untracked_by_class = Counter()
class_names = dict.fromkeys(detection["name"] for detection in ingredients)

for detection in ingredients:
    name = detection["name"]
    track_id = detection["track_id"]

    if track_id is None:
        # Missing IDs cannot be deduplicated, so report these without counting them.
        untracked_by_class[name] += 1
        continue

    frames_by_track[name][track_id].add(detection["frame_number"])

# Calculating quantity estimates for each ingredient class
quantity_estimates = {}

for name in class_names:
    tracks = frames_by_track[name]
    
    quantity = len(tracks) # counts the number of unique track IDs for this ingredient class, which represents the estimated quantity of that ingredient in the video
    
    quantity_estimates[name] = {
        "quantity": quantity,
        "unit": "objects",
        "method": "persistent_unique_track_ids",
        "untracked_detections": untracked_by_class[name],
    }

# Add the final class count to each frame-level detection for convenient access.
for detection in ingredients:
    detection["class_quantity"] = quantity_estimates[detection["name"]]["quantity"]

# Group detections by ingredient and track ID to calculate average confidence.
track_confidences = defaultdict(lambda: defaultdict(list)) # automatically creates a list for each ingredient and track ID

for detection in ingredients:
    name = detection["name"]
    track_id = detection["track_id"]

    if (track_id is not None):
        track_confidences[name][track_id].append(
            detection["confidence"]
        )

# Create a simpler summary for the frontend.
ingredient_summary = []

for name in class_names:
    counted_track_confidences = []

    for track_id, confidences in track_confidences[name].items():
        average_confidence = sum(confidences) / len(confidences) # calculate the average confidence for this track
        counted_track_confidences.append(average_confidence) # add the average confidence to the list of counted track confidences

    average_confidence = (
        sum(counted_track_confidences)
        / len(counted_track_confidences)
        if counted_track_confidences
        else None
    ) # calculates the overall average confidence for this ingredient class across all tracks
    
    ingredient_summary.append({
        "name": name,
        "count": len(counted_track_confidences),
        "confidence": (
            round(average_confidence, 4)
            if average_confidence is not None
            else None
        ),
    })


# Save detections and quantity estimates separately.
with open(INGREDIENTS_OUTPUT_PATH, "w") as f:
    json.dump(ingredients, f, indent=2)

with open(QUANTITY_ESTIMATES_OUTPUT_PATH, "w") as f:
    json.dump(quantity_estimates, f, indent=2)

with open(INGREDIENT_SUMMARY_OUTPUT_PATH, "w") as f:
    json.dump(ingredient_summary, f, indent=2)

print(f"Saved ingredients to {INGREDIENTS_OUTPUT_PATH}")
print(f"Saved quantity estimates to {QUANTITY_ESTIMATES_OUTPUT_PATH}")
print(f"Saved ingredient summary to {INGREDIENT_SUMMARY_OUTPUT_PATH}")