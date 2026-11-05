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
    