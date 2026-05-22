from typing import List
from fastapi import APIRouter, Request
from app.api.routes.auth import get_user_from_header
from app.models.schemas import ChatHistoryItem, DocumentInfo

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/history", response_model=List[ChatHistoryItem])
async def get_user_history(request: Request):
    user = get_user_from_header(request)
    history = request.app.state.db.list_chats(user["id"], limit=100)
    return [ChatHistoryItem(**item) for item in history]


@router.get("/documents", response_model=List[DocumentInfo])
async def get_user_documents(request: Request):
    user = get_user_from_header(request)
    documents = request.app.state.db.list_documents(user["id"])
    return [DocumentInfo(**doc) for doc in documents]
