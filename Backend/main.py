from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from database.configurations import client, user
from database.schemas import UserCreate, UserPublic, Token
from fastapi.middleware.cors import CORSMiddleware
from security import (
    hash_password, verify_password, 
    create_access_token, get_current_user
    )
from routes import scan, ingredients, recipes, pipeline

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

#Connect frontend to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://192.168.1.6:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Creates a new account
@router.post("/register", status_code=201)
async def register_user(new_user: UserCreate):
    username = new_user.username.strip().lower()
    email = new_user.email.lower()
    if not username or not new_user.password:
        raise HTTPException(status_code=400, detail="Username and password are required")
    if await user.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="Username already exists")
    if await user.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Save the user and has password
    await user.insert_one({
        "username": username,
        "email": email,
        "password": hash_password(new_user.password),
        "ingredients": [],
        "saved_recipes": [],
    })
    return {"username": username, "email": email}

# Log in user and issue a token
@router.post("/token", response_model = Token)
async def login_for_access_token(form: OAuth2PasswordRequestForm = Depends()):
    email = form.username.strip().lower()          
    db_user = await user.find_one({"email": email})

    #Error if wrong email or password
    if not db_user or not verify_password(form.password, db_user["password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Token store user id as "sub"
    access_token = create_access_token(data={"sub": str(db_user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}

# Return who is logged in, need a valid token
@router.get("/me", response_model = UserPublic)
async def read_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "email": current_user["email"]}

app.include_router(router)
app.include_router(scan.router)
app.include_router(ingredients.router)
app.include_router(recipes.router)
app.include_router(pipeline.router)
