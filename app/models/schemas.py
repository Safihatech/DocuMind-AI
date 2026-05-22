"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel
from typing import List, Optional, Any


class DocumentMeta(BaseModel):
    id: str
    title: Optional[str]
    source: Optional[str]
    page: Optional[int] = None
    snippet: Optional[str] = None
    uploaded_at: Optional[str] = None
    tags: Optional[List[str]] = None


class QARequest(BaseModel):
    query: str
    top_k: int = 5
    use_hybrid: bool = True
    model: Optional[str] = None
    document_id: Optional[int] = None


class QAResponse(BaseModel):
    answer: str
    citations: List[DocumentMeta] = []
    sources: List[str] = []
    follow_up: Optional[str] = None
    web_search: Optional[List[Any]] = None


class DocumentInfo(BaseModel):
    id: int
    filename: str
    status: str
    uploaded_at: str
    chunks: Optional[int]


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class UserProfile(BaseModel):
    id: int
    name: str
    email: str
    created_at: str


class ChatHistoryItem(BaseModel):
    id: int
    question: str
    answer: str
    created_at: str
