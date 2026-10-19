from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from database.schemas import FindRequest, Recipe
from database.models import recipes_list, recipe_data
from database.configurations import collection, user
from security import get_current_user
# also import your recipe model here if your routes use one, for example:
# from database.models import Recipe

router = APIRouter()

# ---- paste recipes_list() here (the helper that turns Mongo docs into JSON) ----


@router.post("/recipes/find")
async def find_recipes(req: FindRequest):
    items = [i.strip().lower() for i in req.ingredients if i.strip()]
    if not items:
        return []
    recipes = await collection.find({"ner": {"$in": items}}).to_list(length=100)
    s = set(items)
    recipes.sort(key=lambda r: len(set(r["ner"]) & s), reverse=True)
    return recipes_list(recipes)


@router.get("/recipes/saved-ids")
async def get_saved_ids(current_user: dict = Depends(get_current_user)):
    return {"saved": current_user.get("saved_recipes", [])}


@router.get("/recipes/saved")
async def get_saved_recipes(current_user: dict = Depends(get_current_user)):
    ids = []
    for rid in current_user.get("saved_recipes", []):
        try:
            ids.append(ObjectId(rid))
        except InvalidId:
            pass
    recipes = await collection.find({"_id": {"$in": ids}}).to_list(length=200)
    return recipes_list(recipes)


@router.post("/recipes/save/{recipe_id}")
async def save_recipe(recipe_id: str, current_user: dict = Depends(get_current_user)):
    try:
        oid = ObjectId(recipe_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid recipe id")
    if not await collection.find_one({"_id": oid}):
        raise HTTPException(status_code=404, detail="Recipe not found")
    await user.update_one({"_id": current_user["_id"]}, {"$addToSet": {"saved_recipes": recipe_id}})
    doc = await user.find_one({"_id": current_user["_id"]}, {"saved_recipes": 1})
    return {"saved": doc.get("saved_recipes", [])}


@router.post("/recipes/unsave/{recipe_id}")
async def unsave_recipe(recipe_id: str, current_user: dict = Depends(get_current_user)):
    await user.update_one({"_id": current_user["_id"]}, {"$pull": {"saved_recipes": recipe_id}})
    doc = await user.find_one({"_id": current_user["_id"]}, {"saved_recipes": 1})
    return {"saved": doc.get("saved_recipes", [])}

@router.get("/recipes/browse")
async def browse_recipes(limit: int = 10, skip: int = 0):
    limit = min(limit, 30)    # cap it so nobody can pull the whole database
    docs = await collection.find({}).skip(skip).limit(limit).to_list(length=limit)
    return recipes_list(docs)

@router.get("/recipes/{recipe_id}")
async def get_recipe(recipe_id: str):
    try:
        oid = ObjectId(recipe_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Recipe not found")
    doc = await collection.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe_data(doc)

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
