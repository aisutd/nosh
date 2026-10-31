from fastapi import APIRouter, Depends, HTTPException
from database.configurations import inventory
from security import get_current_user
from pymongo import ReturnDocument
from database.schemas import InventoryItem, ConsumeRequest
from retrieval.ingredients import normalize_name, required_ingredients, PANTRY
import re
import unicodedata

router = APIRouter()


# Turn a Mongo document into what the API sends back
def item_out(doc):
    return {"name": normalize_name(doc["name"].strip().lower()), "quantity": doc["quantity"], "unit": doc["unit"]}


# GET /inventory: everything this user has in stock, sorted by name
@router.get("/inventory")
async def get_inventory(current_user: dict = Depends(get_current_user)):
    docs = await inventory.find({"user_id": current_user["_id"]}).sort("name", 1).to_list(length=500)
    return [item_out(d) for d in docs]


# PUT /inventory: add an item, or set its quantity if it already exists
@router.put("/inventory")
async def set_item(item: InventoryItem, current_user=Depends(get_current_user)):
    name = normalize_name(item.name)          # same cleanup as item_out
    doc = await inventory.find_one_and_update(
        {"user_id": current_user["_id"], "name": name},   # match on the cleaned name
        {"$set": {"quantity": item.quantity, "unit": item.unit}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return item_out(doc)


# DELETE /inventory/{name}: remove an item completely
@router.delete("/inventory/{name}")
async def delete_item(name: str, current_user: dict = Depends(get_current_user)):
    result = await inventory.delete_one({"user_id": current_user["_id"], "name": normalize_name(name)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"deleted": name}

LOW_STOCK = 1                    # warn when this much or less is left

# measuring units we recognize (everything else, like "large" or "cloves", counts as plain items)
MEASURES = {
    "cup": "cup", "cups": "cup",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp",
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp",
    "pound": "lb", "pounds": "lb", "lb": "lb", "lbs": "lb",
    "ounce": "oz", "ounces": "oz", "oz": "oz",
    "gram": "g", "grams": "g", "g": "g", "kg": "kg", "ml": "ml",
    "liter": "l", "liters": "l", "pinch": "pinch",
}

# "4 large eggs" -> (4.0, None)   "1 1/2 cups flour" -> (1.5, "cup")   "salt" -> (1, None)
def parse_amount(line):
    text = unicodedata.normalize("NFKC", line.lower()).replace("\u2044", "/")   # turns ½ into 1/2
    m = re.match(r"\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s*([a-z]+)?", text)
    if not m:
        return 1, None
    num = m.group(1)
    if " " in num:                                  # mixed number: "1 1/2"
        whole, frac = num.split()
        a, b = frac.split("/")
        amount = int(whole) + int(a) / int(b)
    elif "/" in num:                                # fraction: "1/2"
        a, b = num.split("/")
        amount = int(a) / int(b)
    else:
        amount = float(num)
    return (amount or 1), MEASURES.get(m.group(2) or "")

# every measure -> (kind, size in a base unit: ml for volume, g for weight)
BASE = {
    "tsp": ("vol", 4.93), "tbsp": ("vol", 14.79), "cup": ("vol", 236.6),
    "ml": ("vol", 1), "l": ("vol", 1000),
    "g": ("wt", 1), "kg": ("wt", 1000), "oz": ("wt", 28.35), "lb": ("wt", 453.6),
}

# units that are really "how many things": taking 1 is a fair guess for these
COUNTABLE = {"count", "can", "package", "bottle", "jar", "bunch", "head", "slice", "stick", "clove"}


# 2 tbsp -> cups, 8 oz -> lb ... returns None if the units aren't the same kind
def convert(amount, src, dst):
    a, b = BASE.get(src), BASE.get(dst)
    if a and b and a[0] == b[0]:
        return amount * a[1] / b[1]
    return None

# POST /inventory/consume: subtract a cooked recipe's ingredients, return warnings
@router.post("/inventory/consume")
async def consume(req: ConsumeRequest, current_user: dict = Depends(get_current_user)):
    updated, warnings = [], []

    for line in req.ingredients:
        amount, unit = parse_amount(line)
        for name in sorted((required_ingredients(line) or set()) - PANTRY):
            doc = await inventory.find_one({"user_id": current_user["_id"], "name": name})
            if doc is None:
                warnings.append(f"{name} isn't in your inventory")
                continue

            # work out how much to take off, in the unit the inventory uses
            if unit is None and doc["unit"] == "count":
                deduct = amount                                    # "4 eggs" from a count
            elif unit == doc["unit"]:
                deduct = amount                                    # same unit
            else:
                deduct = convert(amount, unit, doc["unit"]) if unit else None   # tbsp -> cup, oz -> lb
                if deduct is None:                                 # not convertible (cup vs lb...)
                    if doc["unit"] in COUNTABLE:
                        deduct = 1                                 # can / package / count: take 1
                    else:
                        warnings.append(
                            f"Couldn't convert {unit or 'the recipe amount'} to {doc['unit']} for {name}; please check your amount"
                        )
                        continue                                   # don't guess, leave it alone
            deduct = round(deduct, 2)                              # no 0.0625000001 in the list

            doc = await inventory.find_one_and_update(
                {"_id": doc["_id"]},
                {"$inc": {"quantity": -deduct}},
                return_document=ReturnDocument.AFTER,
            )
            if doc["quantity"] <= 0:
                await inventory.update_one({"_id": doc["_id"]}, {"$set": {"quantity": 0}})   # never go negative
                doc["quantity"] = 0
                warnings.append(f"You've run out of {name}")
            elif doc["quantity"] <= LOW_STOCK:
                warnings.append(f"Only {doc['quantity']:g} {name} left")
            updated.append(item_out(doc))

    return {"updated": updated, "warnings": warnings}