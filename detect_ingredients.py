from ultralytics import YOLO # import the yolo model from ultralytics library
import json # imports the json library to save the results in a json file
from pathlib import Path # imports the Path class from the pathlib library to handle file paths
import cv2 # imports OpenCV, allowing us to run inference on video files

# File Paths
BASE_DIR = Path(__file__).resolve().parent # finds the folder where the script is located

MODEL_PATH = BASE_DIR / "best.pt" # finds the path to the trained model file (best.pt) in the same folder as the script
VIDEO_PATH = BASE_DIR / "test_videos" / "fridge_scan.mp4" # finds the path to the test video in the test_videos folder located in the same folder as the script
OUTPUT_PATH = BASE_DIR / "detections.json" # finds the path to the output json file (detections.json) in the same folder as the script

# Getting the video FPS
cap = cv2.VideoCapture(str(VIDEO_PATH))
fps = cap.get(cv2.CAP_PROP_FPS)
cap.release()

if fps <= 0:
    raise ValueError("Could not read a valid FPS from the video.")

model = YOLO(str(MODEL_PATH)) # loads the trained YOLO model from the specified path (best.pt) using the ultralytics library and stores it in the variable "model"

results = model.track(
    source=str(VIDEO_PATH),
    tracker="bytetrack.yaml",
    stream=True,
    persist=True,
    save=True,
    name="annotated_test_result",
    verbose=False
) # runs the model on the specified test video and stores the results in the variable "results"

ingredients = [] # initializes an empty list to store the detected ingredients and their confidence scores

# Loop through the results and extract the detected ingredients and their confidence scores
for frame_number, result in enumerate(results):
    timestamp = frame_number / fps
    
    for box in result.boxes:
        class_id = int(box.cls[0]) # gets the class ID of the detected ingredient from the box object
        confidence = float(box.conf[0]) # gets the confidence score of the detected ingredient from the box object
        name = result.names[class_id] # gets the name of the detected ingredient using the class ID and the names dictionary in the result object

        track_id = None # assumes that the detection doesn't have a tracking id yet
        if box.id is not None:
            track_id = int(box.id[0]) # gets the tracking id and converts it to an integer if there is a tracking id

        # appends the detected ingredient, its confidence score, the tracking id, and the timestamp to the ingredients list
        ingredients.append({
            "name": name,
            "confidence": round(confidence, 4),
            "track_id": track_id,
            "timestamp": round(timestamp, 3)
        })

# saves the detected ingredients and their confidence scores to a json file
with open(OUTPUT_PATH, "w") as f:
    json.dump({"ingredients": ingredients}, f, indent=2) # saves the ingredients list as a json object with the key "ingredients" and writes it to the specified output path (detections.json) with an indentation of 2 spaces for better readability

# prints a message indicating that the detections have been saved to the specified output path
print(f"Saved detections to {OUTPUT_PATH}")