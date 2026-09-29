# Items API
Basic CRUD API built with FastAPI.

## Run
pip install -r requirements.txt
uvicorn APITest:app --reload

Docs at http://127.0.0.1:8000/docs

## Endpoints
- GET    /items          list all items
- GET    /items/{id}     get one item
- POST   /items          create an item
- PUT    /items/{id}     update an item
- DELETE /items/{id}     delete an item