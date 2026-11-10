from ultralytics import YOLO # import the yolo model from ultralytics library
import json # imports the json library to save the results in a json file
from pathlib import Path # imports the Path class from the pathlib library to handle file paths
import cv2 # imports OpenCV, allowing us to run inference on video files
from collections import Counter, defaultdict # imports the Counter and defaultdict classes from the collections library to count the number of detections for each ingredient class and to group detections by ingredient and track ID, respectively
import random # imports the random library to generate random colors for the bounding boxes and labels

# File Paths
BASE_DIR = Path(__file__).resolve().parent # finds the folder where the script is located

MODEL_PATH = BASE_DIR / "best.pt" # finds the path to the trained model file (best.pt) in the same folder as the script
VIDEO_PATH = BASE_DIR / "test_videos" / "sample2.mp4" # finds the path to the test video in the test_videos folder located in the same folder as the script
INGREDIENTS_OUTPUT_PATH = BASE_DIR / "ingredients.json"
INGREDIENT_SUMMARY_OUTPUT_PATH = BASE_DIR / "ingredient_summary.json"
ANNOTATED_VIDEO_OUTPUT_PATH = BASE_DIR / "annotated_video.mp4" # finds the path to the output video file (annotated_video.mp4) in the same folder as the script

# Label Placement Helpers
def rectangles_overlap(rect1, rect2):
    x1_min, y1_min, x1_max, y1_max = rect1
    x2_min, y2_min, x2_max, y2_max = rect2

    return not (x1_max < x2_min or x1_min > x2_max or y1_max < y2_min or y1_min > y2_max)

color_map = {} # initializes an empty dictionary to store the colors for each ingredient class

# Generates a random color for each ingredient class and stores it in the color_map dictionary
def get_color(name):
    if name not in color_map:
        color_map[name] = (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255)
        )
    return color_map[name]

# Draws a label above or below the bounding box, avoiding overlap with other labels
def draw_label(frame, name, x_min, y_min, x_max, y_max, occupied_labels):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1.1
    thickness = 2
    padding = 7
    color = get_color(name)

    (w, h), _ = cv2.getTextSize(name, font, scale, thickness)

    label_w = w + 2 * padding
    label_h = h + 2 * padding

    # draws the ingredient bounding box
    cv2.rectangle(frame, (x_min, y_min), (x_max, y_max), color, 3)

    # some possible label positions
    positions = [
        (x_min, y_min - label_h),
        (x_min, y_max),
        (x_min - label_w, y_min),
        (x_max, y_min)
    ]

    available_position = None # initializes a variable to store the available position for the label

    # checks each possible label position to see if it overlaps with any previously occupied label positions
    for x, y in positions:
        x = max(0, min(x, frame.shape[1] - label_w)) # ensures that the label does not go outside the frame boundaries
        y = max(0, min(y, frame.shape[0] - label_h)) # ensures that the label does not go outside the frame boundaries

        label = (x, y, x + label_w, y + label_h) # defines the bounding box for the label based on the current position being checked

        # checks if the current label position overlaps with any previously occupied label positions
        if not any(rectangles_overlap(label, r) for r in occupied_labels):
            available_position = label
            break

    # fallback if all positions are occupied
    if available_position is None:
        x = max(0, min(x_min, frame.shape[1] - label_w)) # ensures that the label does not go outside the frame boundaries
        y = max(0, min(y_min - label_h, frame.shape[0] - label_h)) # ensures that the label does not go outside the frame boundaries
        available_position = (x, y, x + label_w, y + label_h) # defines the bounding box for the label based on the fallback position

    # saves the occupied position
    occupied_labels.append(available_position) # adds the bounding box for the label to the list of occupied label positions to avoid overlapping labels in future iterations

    x, y, _, _ = available_position # unpacks the coordinates of the available position for the label into separate variables for easier use in drawing the label on the frame

    # draws the label background
    cv2.rectangle(
        frame,
        (x, y),
        (x + label_w, y + label_h),
        color,
        -1
    )

    # draws the ingredient name
    cv2.putText(
        frame,
        name,
        (x + padding, y + h + padding),
        font,
        scale,
        (255, 255, 255),
        thickness,
        cv2.LINE_AA
    )

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
    source = str(VIDEO_PATH),
    tracker = "bytetrack.yaml",
    stream = True, # streams the video frames to the model for processing
    persist = True, # keeps the model's state between frames, allowing it to track objects across multiple frames
    save = False, # does not save the processed video frames to disk
    verbose = False # suppresses detailed output from the model during processing
) # runs the model on the specified test video and stores the results in the variable "results"

ingredients = [] # initializes an empty list to store the detected ingredients and their confidence scores
video_writer = None # initializes a variable to store the video writer object, which will be used to save the processed video frames with bounding boxes and labels drawn on them

# Loop through the results and extract the detected ingredients and their confidence scores
for frame_number, result in enumerate(results):
    timestamp = frame_number / fps
    frame = result.orig_img.copy()
    occupied_labels = [] # resets the list of occupied label positions for each frame to avoid overlapping labels

    # initializes video_writer using the first processed frame
    if (video_writer is None):
        height, width = frame.shape[:2]

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")

        video_writer = cv2.VideoWriter(
            str(ANNOTATED_VIDEO_OUTPUT_PATH),
            fourcc,
            fps,
            (width, height)
        )

        if not video_writer.isOpened():
            raise ValueError("Could not create annotated video.")
    
    if result.boxes is None:
        continue
    
    for box in result.boxes:
        class_id = int(box.cls[0]) # gets the class ID of the detected ingredient from the box object
        confidence = float(box.conf[0]) # gets the confidence score of the detected ingredient from the box object
        name = result.names[class_id] # gets the name of the detected ingredient using the class ID and the names dictionary in the result object
        
        track_id = None # assumes that the detection doesn't have a tracking id yet
        
        if box.id is not None:
            track_id = int(box.id[0]) # gets the tracking id and converts it to an integer if there is a tracking id

        # bounding box coordinates
        box_coordinates = [round(coord, 2) for coord in box.xyxy[0].tolist()] # gets the bounding box coordinates of the detected ingredient from the box object and rounds them to 2 decimal places

        # draws the bounding box and label on the frame
        x1, y1, x2, y2 = map(int, box_coordinates)

        # adds ingredient name only
        draw_label(frame, name, x1, y1, x2, y2, occupied_labels)
        
        # appends the detected ingredient, its confidence score, tracking id, timestamp, and bounding box coordinates to the ingredients list
        ingredients.append({
            "name": name,
            "confidence": round(confidence, 4),
            "track_id": track_id,
            "frame_number": frame_number,
            "timestamp": round(timestamp, 3),
            "box": box_coordinates
        })

    video_writer.write(frame) # writes the processed frame with bounding boxes and labels to the output video file

# Releases The Output Video
if (video_writer is not None):
    video_writer.release() # releases the video writer object when finished

print("Total Detections:", len(ingredients))

# Group detections by ingredient and track ID to calculate average confidence.
track_confidences = defaultdict(lambda: defaultdict(list)) # automatically creates a list for each ingredient and track ID
untracked_by_class = Counter() # counts the number of detections for each ingredient class that do not have a tracking ID, which means they cannot be deduplicated and counted towards the estimated quantity of that ingredient in the video.
class_names = dict.fromkeys(detection["name"] for detection in ingredients) # creates a dictionary with the names of the detected ingredients as keys and None as values

for detection in ingredients:
    name = detection["name"]
    track_id = detection["track_id"]

    if (track_id is None):
        untracked_by_class[name] += 1 # increments the count of untracked detections for this ingredient class
        continue

    track_confidences[name][track_id].append(detection["confidence"]) # adds the confidence score of the detection to the list of confidences for that ingredient and track ID

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
        "quantity": len(track_confidences[name]),
        "average_confidence": round(average_confidence, 4) if average_confidence is not None else None
        }
    ) 

# Save detections and quantity estimates separately.
with open(INGREDIENTS_OUTPUT_PATH, "w") as f:
    json.dump(ingredients, f, indent=2)

with open(INGREDIENT_SUMMARY_OUTPUT_PATH, "w") as f:
    json.dump(ingredient_summary, f, indent=2)

print(f"Saved ingredients to {INGREDIENTS_OUTPUT_PATH}")
print(f"Saved ingredient summary to {INGREDIENT_SUMMARY_OUTPUT_PATH}")
print(f"Saved annotated video to {ANNOTATED_VIDEO_OUTPUT_PATH}")