from typing import List
from fastapi import APIRouter, HTTPException, Request, status
from app.models.schemas import ChatHistoryItem

router = APIRouter(prefix="/history", tags=["history"])


def get_current_user(request: Request):
    user_id = request.headers.get('x-user-id')
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-User-ID header.")
    try:
        user_id_int = int(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-User-ID header.")
    user = request.app.state.db.get_user_by_id(user_id_int)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user


@router.get("/", response_model=List[ChatHistoryItem])
async def get_history(request: Request):
    user = get_current_user(request)
    history = request.app.state.db.list_chats(user["id"], limit=50)
    return [ChatHistoryItem(**item) for item in history]
