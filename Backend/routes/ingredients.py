from fastapi import APIRouter, Depends, HTTPException

from database.configurations import user
from security import get_current_user

router = APIRouter()



async def get_user_ingredients(user_id):
    """Read one user's ingredient list straight from their own document."""
    doc = await user.find_one({"_id": user_id}, {"ingredients": 1})
    return doc.get("ingredients", []) if doc else []


@router.get("/ingredients")
async def get_ingredients(current_user: dict = Depends(get_current_user)):
    # get_current_user turns the token into this user's document
    return {"ingredients": current_user.get("ingredients", [])}


@router.post("/ingredients/add")
async def add_ingredients(ingredient: str, current_user: dict = Depends(get_current_user)):
    item = ingredient.strip().lower()
    if not item:
        raise HTTPException(status_code=400, detail="Ingredient cannot be empty")
    # $addToSet adds the item to this user's array only if it isn't already there
    await user.update_one({"_id": current_user["_id"]}, {"$addToSet": {"ingredients": item}})
    return {"ingredients": await get_user_ingredients(current_user["_id"])}

@router.post("/ingredients/remove")
async def remove_ingredients(ingredient: str, current_user: dict = Depends(get_current_user)):
    item = ingredient.strip().lower()
    if not item:
        raise HTTPException(status_code=400, detail="Ingredient cannot be empty")
    # $pull removes that item from this user's array
    await user.update_one({"_id": current_user["_id"]}, {"$pull": {"ingredients": item}})
    return {"ingredients": await get_user_ingredients(current_user["_id"])}