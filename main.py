from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from bson import ObjectId
from database.configurations import client, collection
from database.models import Recipe, Ingredient_List
from database.schemas import recipes_list

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

app.include_router(router)