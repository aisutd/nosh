import os
import certifi
from pymongo import AsyncMongoClient
from dotenv import load_dotenv

# load in variable in .env folder
load_dotenv()

# Connect to the Mongo DB Atlas database
client = AsyncMongoClient(
    os.getenv("MONGO_URI"),
    tlsCAFile=certifi.where()
)
db = client.recipecluster
collection = db.recipes
user = db.user