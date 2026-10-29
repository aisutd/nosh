"""TEST ONLY: direct UI fixture; in-memory data disappears on exit.
Never imported by main.py. Fixture login is not production authentication.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from test_personalization import FakeUsers
from routes import memory, voice
import security

store = FakeUsers()
for document in store.docs.values():
    document['username'] = 'Memory demo'
memory.user = security.user = store
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173'], allow_methods=['*'], allow_headers=['*'])
app.include_router(memory.router)
app.include_router(voice.router)


@app.post('/token')
async def fixture_login(form: OAuth2PasswordRequestForm = Depends()):
    return {'access_token': security.create_access_token({'sub': store.ids['a']}), 'token_type': 'bearer'}


@app.get('/me')
async def me(current_user=Depends(security.get_current_user)):
    return {'username': current_user['username'], 'email': 'demo@example.com'}


@app.get('/ingredients')
async def ingredients():
    return {'ingredients': []}


@app.get('/recipes/saved-ids')
async def saved():
    return {'saved': []}


@app.get('/recipes/demo')
async def recipe():
    return {'title': 'Garlic toast', 'ingredients': ['bread', 'garlic'], 'directions': ['Toast bread.', 'Rub with garlic.']}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
