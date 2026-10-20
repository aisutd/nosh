from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form
from bson import ObjectId
from database.configurations import client, collection
from database.models import Recipe, Ingredient_List
from database.schemas import recipes_list
from pydantic import BaseModel, Field
from fastapi.concurrency import run_in_threadpool
from nosh_pipeline import run_nosh
from vision.detector import detect_ingredients

#Check and print connection to MongoDB is successful
@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await client.admin.command('ping')
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
    yield

# Initialize FastAPI app and router
app = FastAPI(lifespan=lifespan)
router = APIRouter()

#================================================================
#Temporary code: Testing user ingredient list and recipe searches
#================================================================

#Store the current list of ingredients
currently_ingredients = [] 

#Add ingredients to user list
@router.post("/ingredients/add")
async def add_ingredients(ingredient: str):
    currently_ingredients.append(ingredient)
    return {"ingredients": currently_ingredients}

#Remove ingredients from user list
@router.post("/ingredients/remove")
async def remove_ingredients(ingredient: str):
    currently_ingredients.remove(ingredient)
    return {"ingredients": currently_ingredients}

#Find recipes based on user ingredients
#Sort recipes by the number of matching ingredients
@router.post("/recipes/find")
async def find_recipes():
    query = {"ner": {"$in": currently_ingredients}}
    recipes = await collection.find(query).to_list(length=100)
    ingredient_set = set(currently_ingredients)
    recipes.sort(
        key=lambda recipe: len(set(recipe["ner"]) & ingredient_set),
        reverse=True,
    )
    return recipes_list(recipes)

#===================================================================
#Temporary code: Testing CRUD operations for recipes in the database
#===================================================================

#Get all recipes from the database
@router.get("/",)
async def get_recipes():
    try:
        recipes = await collection.find({}).to_list(length=100)
        return recipes_list(recipes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching recipes: {str(e)}")

#Create a new recipe in the database
@router.post("/")
async def create_recipe(new_recipe: Recipe):
    try: 
        result = await collection.insert_one(dict(new_recipe))
        return{"status_code": 201, "message": "Recipe created successfully", "recipe_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error inserting recipe: {str(e)}")

#Update an existing recipe in the database
@router.put("/{recipe_id}")
async def update_recipe(recipe_id: str, updated_recipe: Recipe):
    try:
        id = ObjectId(recipe_id)
        existing_recipe = await collection.find_one({"_id": id})
        if not existing_recipe:
            raise HTTPException(status_code=404, detail=f"Recipe with id {recipe_id} not found")
        result = await collection.update_one({"_id": id}, {"$set": dict(updated_recipe)})
        return {"status_code": 200, "message": "Recipe updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating recipe: {str(e)}")

#Delete a recipe from the database
@router.delete("/{recipe_id}")
async def delete_recipe(recipe_id: str):
    try:
        id = ObjectId(recipe_id)
        existing_recipe = await collection.find_one({"_id": id})
        if not existing_recipe:
            raise HTTPException(status_code=404, detail=f"Recipe with id {recipe_id} not found")
        result = await collection.delete_one({"_id": id})
        return {"status_code": 200, "message": "Recipe deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting recipe: {str(e)}")
    

#
# Code for the /recipes/from-detections endpoint
#    
class IngredientDetection(BaseModel):
    name: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class DetectionOutput(BaseModel):
    ingredients: list[IngredientDetection]


class RecipeFromDetectionsRequest(BaseModel):
    detections: DetectionOutput
    user_query: str = ""


async def generate_from_detections(detections: DetectionOutput, user_query: str):
    ingredients = sorted({
        item.name.replace("_", " ").strip().lower()
        for item in detections.ingredients
        if item.name.replace("_", " ").strip()
    })

    if not ingredients:
        raise HTTPException(status_code=400, detail="No ingredient names were detected or provided.")

    result = await run_in_threadpool(run_nosh, ingredients, user_query=user_query)
    return {
        "detections": detections.model_dump(),
        "ingredients": ingredients,
        "result": result,
    }


@router.post("/recipes/from-detections")
async def recipes_from_detections(request: RecipeFromDetectionsRequest):
    return await generate_from_detections(request.detections, request.user_query)


MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/recipes/from-image")
async def recipes_from_image(
    image: UploadFile = File(...),
    user_query: str = Form(""),
):
    """Detect ingredients in an image and generate a recipe from retrieved sources."""
    try:
        image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    finally:
        await image.close()

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")

    try:
        output = await run_in_threadpool(detect_ingredients, image_bytes)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="The ingredient detection model is unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await generate_from_detections(DetectionOutput.model_validate(output), user_query)


app.include_router(router)
