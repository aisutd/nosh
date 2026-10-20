from datetime import UTC, datetime, timedelta
import jwt
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from database.setting import settings
from fastapi import Depends, HTTPException
from bson import ObjectId
from bson.errors import InvalidId
from database.configurations import user


# Hasher using the recommended algorithm (Argon2).
password_hash = PasswordHash.recommended()

# Login happens at the "/token" route
# On protected routes, look for the token in the "Authorization: Bearer ..." header
# It also adds the Authorize button to /docs.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def hash_password(password: str) -> str:
    # Hash the password and return
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verify that the plain password match with hash and return True or False
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    # Create a JWT access token

    # Create copy of data and add an expiration time
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes,
        )
    to_encode.update({"exp": expire})

    # Encodes using secret key
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )
    return encoded_jwt

def verify_access_token(token: str) -> str | None:
    # Verify a JWT access token and return the subject (user id) if valid
    try:
        # Verify token using secret key
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            # Token must have expiration date and user id (sub = id)
            options={"require": ["exp", "sub"]},
        )
    # Return none if token is invalid or expired
    except jwt.InvalidTokenError:
        return None
    return payload.get("sub")

"""
Video Explanations:
A JSON web token has three parts. So it has a header which contains the algorithm and type, 
a payload which contains our data plus the expiration, and a signature which proves the token 
wasn't tampered with. And all three parts are B 64 encoded and separated by dots. The signature 
is created using our secret key. So only our server can create valid tokens.
"""

# Turn token on the request into a user
async def get_current_user(token: str = Depends(oauth2_scheme)):
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    try:
        db_user = await user.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")
    return db_user
