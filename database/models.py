from pydantic import BaseModel

# The Recipe model/class
class Recipe(BaseModel):
    title: str
    ingredients: list[str]
    directions: list[str]
    link: str
    ner: list[str]

# The user ingredient list model/class
class Ingredient_List(BaseModel):
    ingredients: list[str] = []