from ultralytics import YOLO # import the yolo model from ultralytics library
import json # imports the json library to save the results in a json file
from pathlib import Path # imports the Path class from the pathlib library to handle file paths

BASE_DIR = Path(__file__).resolve().parent # finds the folder where the script is located

MODEL_PATH = BASE_DIR / "best.pt" # finds the path to the trained model file (best.pt) in the same folder as the script
IMAGE_PATH = BASE_DIR / "test_images" / "sample2.jpg" # finds the path to the test image (sample2.jpg) in the test_images folder located in the same folder as the script
OUTPUT_PATH = BASE_DIR / "detections.json" # finds the path to the output json file (detections.json) in the same folder as the script

model = YOLO(str(MODEL_PATH)) # loads the trained YOLO model from the specified path (best.pt) using the ultralytics library
results = model(str(IMAGE_PATH)) # runs the model on the specified test image (sample2.jpg) and stores the results in the variable "results"
results[0].save(filename=str(BASE_DIR / "annotated_sample2.jpg")) # saves the annotated image with detected ingredients to a new file (annotated_sample2.jpg) in the same folder as the script

ingredients = [] # initializes an empty list to store the detected ingredients and their confidence scores

# Loop through the results and extract the detected ingredients and their confidence scores
for result in results:
    for box in result.boxes:
        class_id = int(box.cls[0]) # gets the class ID of the detected ingredient from the box object
        confidence = float(box.conf[0]) # gets the confidence score of the detected ingredient from the box object

        name = result.names[class_id] # gets the name of the detected ingredient using the class ID and the names dictionary in the result object

        # appends the detected ingredient and its confidence score to the ingredients list
        ingredients.append({
            "name": name,
            "confidence": round(confidence, 4)
        })

# saves the detected ingredients and their confidence scores to a json file
with open(OUTPUT_PATH, "w") as f:
    json.dump({"ingredients": ingredients}, f, indent=2) # saves the ingredients list as a json object with the key "ingredients" and writes it to the specified output path (detections.json) with an indentation of 2 spaces for better readability

# prints a message indicating that the detections have been saved to the specified output path
print(f"Saved detections to {OUTPUT_PATH}")