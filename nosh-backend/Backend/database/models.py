# Function to convert a recipe document from the database into a dictionary format
def recipe_data(recipe) -> dict:
    return {
        "id": str(recipe["_id"]),
        "title": recipe["title"],
        "ingredients": recipe["ingredients"],
        "directions": recipe["directions"],
        "link": recipe["link"],
        "ner": recipe["ner"],
        "image": recipe.get("image"),
        "kind": recipe.get("kind", "mongo"),
    }

# Converts a whole list of recipe documents (calls recipe_data on each one)
def recipes_list(recipes) -> list:
    return [recipe_data(recipe) for recipe in recipes]