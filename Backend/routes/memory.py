"""Per-account explicit preferences and up to 30 recent session feedback entries."""
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends
from database.configurations import user
from security import get_current_user
from personalization import Preferences, SessionFeedback

router = APIRouter(prefix='/memory', tags=['personalization'])


def public_memory(document):
    return {'preferences': Preferences.model_validate(document.get('cooking_preferences') or {}).model_dump(),
            'sessions': document.get('cooking_history', [])[-30:]}


@router.get('')
async def get_memory(current_user: dict = Depends(get_current_user)):
    return public_memory(current_user)


@router.put('/preferences')
async def save_preferences(preferences: Preferences, current_user: dict = Depends(get_current_user)):
    await user.update_one({'_id': current_user['_id']}, {'$set': {'cooking_preferences': preferences.model_dump()}})
    return {'preferences': preferences.model_dump()}


@router.post('/sessions', status_code=201)
async def save_session(feedback: SessionFeedback, current_user: dict = Depends(get_current_user)):
    entry = {**feedback.model_dump(), 'id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat()}
    await user.update_one({'_id': current_user['_id']}, {'$push': {'cooking_history': {'$each': [entry], '$slice': -30}}})
    return {'session': entry}


@router.delete('')
async def clear_memory(current_user: dict = Depends(get_current_user)):
    await user.update_one({'_id': current_user['_id']}, {'$unset': {'cooking_preferences': '', 'cooking_history': ''}})
    return public_memory({})
