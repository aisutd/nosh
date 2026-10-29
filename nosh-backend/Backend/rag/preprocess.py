import os
from pathlib import Path

import kagglehub
import pandas as pd


# Download the latest version of the Kaggle recipe dataset
path = kagglehub.dataset_download(
    "thedevastator/better-recipes-for-a-better-life"
)

print("Dataset path:", path)
print("Files:\n", os.listdir(path))


# Load the main recipes CSV
csv_path = os.path.join(path, "recipes.csv")
df = pd.read_csv(csv_path)

print("Original rows:", len(df))
print("Original columns:\n", df.columns)


"""
Preprocessing:
- Remove duplicate rows
- Remove rows missing required recipe information
- Remove rows with empty required fields
- Remove unnecessary CSV index column
- Clean extra whitespace
- Create one recipe chunk for embedding
"""


# Remove exact duplicate rows
df = df.drop_duplicates()


# These are the fields we need
required_fields = [
    "recipe_name",
    "ingredients",
    "directions"
]


# Remove rows missing any required field
df = df.dropna(subset=required_fields)


# Remove rows where required fields are empty strings
for field in required_fields:
    df = df[df[field].astype(str).str.strip() != ""]


# Remove unecessary index column from csv
if "Unnamed: 0" in df.columns:
    df = df.drop(columns=["Unnamed: 0"])


# Clean extra whitespace
df["recipe_name"] = df["recipe_name"].astype(str).str.strip()
df["ingredients"] = df["ingredients"].astype(str).str.strip()
df["directions"] = df["directions"].astype(str).str.strip()


# Create one chunk per recipe
# This text will later be converted into an embedding
def create_chunk(row):
    return (
        f"Recipe: {row['recipe_name']}\n"
        f"Ingredients: {row['ingredients']}\n"
        f"Directions: {row['directions']}"
    )


df["chunk"] = df.apply(create_chunk, axis=1)


# Print results
print("Rows after preprocessing:", len(df))
print("Columns after preprocessing:\n", df.columns)

print("\nExample recipe chunk:\n")
print(df["chunk"].iloc[0])


# Save cleaned and chunked dataset
output_path = Path(__file__).resolve().parents[1] / "data" / "processed" / "cleaned_recipes.csv"
output_path.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_path, index=False)

print("\nSaved cleaned dataset to:", output_path)