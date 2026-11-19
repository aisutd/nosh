from fastapi import APIRouter, Depends, HTTPException

from database.configurations import user
from security import get_current_user
from database.configurations import inventory
from retrieval.ingredients import normalize_name
from fastapi.concurrency import run_in_threadpool
from retrieval.ingredient_validation import validate_ingredient

router = APIRouter()

# Gets one user's ingredient list from the database
async def get_user_ingredients(user_id):
    """Read one user's ingredient list straight from their own document."""
    doc = await user.find_one({"_id": user_id}, {"ingredients": 1})
    return doc.get("ingredients", []) if doc else []

# Get the logged-in user's ingredients
@router.get("/ingredients")
async def get_ingredients(current_user: dict = Depends(get_current_user)):
    # get_current_user turns the token into this user's document
    return {"ingredients": current_user.get("ingredients", [])}

# Add an ingredient
@router.post("/ingredients/add")
async def add_ingredients(
    ingredient: str,
    current_user: dict = Depends(get_current_user),
):
    if len(ingredient) > 200:
        raise HTTPException(400, "Ingredient name is too long.")

    try:
        item = await run_in_threadpool(validate_ingredient, ingredient)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            503, "Ingredient validation data is unavailable."
        ) from exc

    await user.update_one(
        {"_id": current_user["_id"]},
        {"$addToSet": {"ingredients": item}},
    )

    await inventory.update_one(
        {"user_id": current_user["_id"], "name": item},
        {"$setOnInsert": {"quantity": 1, "unit": "count"}},
        upsert=True,
    )

    return {
        "ingredients": await get_user_ingredients(current_user["_id"])
    }


# Remove an ingredient
@router.post("/ingredients/remove")
async def remove_ingredients(ingredient: str, current_user: dict = Depends(get_current_user)):
    item = ingredient.strip().lower()
    if not item:
        raise HTTPException(status_code=400, detail="Ingredient cannot be empty")
    # $pull removes that item from this user's array
    await user.update_one({"_id": current_user["_id"]}, {"$pull": {"ingredients": item}})
    return {"ingredients": await get_user_ingredients(current_user["_id"])}