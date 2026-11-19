from pydantic import BaseModel, EmailStr, Field

# The Recipe model/class
class Recipe(BaseModel):
    title: str
    ingredients: list[str]
    directions: list[str]
    link: str
    ner: list[str]


# User model/class for user registration/creation
class UserCreate(BaseModel):
    username: str = Field(min_length = 1, max_length = 100)
    password: str = Field(max_length = 100)
    email: EmailStr = Field(min_length = 8)

#What API is allow to return
class UserPublic(BaseModel):
    username: str
    email: EmailStr

# What /token returns
class Token(BaseModel):
    access_token: str
    token_type: str

# Request recipes
class FindRequest(BaseModel):
    ingredients: list[str]

# One inventory item as sent to / from the API
class InventoryItem(BaseModel):
    name: str = Field(min_length=1, max_length=100)   
    quantity: float = Field(ge=0)                 
    unit: str = "count"  

# What the frontend sends when a recipe is marked as cooked
class ConsumeRequest(BaseModel):
    ingredients: list[str]       # the recipe's ingredient lines, e.g. ["4 large eggs", "1 cup flour"]                            