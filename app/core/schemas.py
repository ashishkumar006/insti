"""Shared request/response schemas (thin)."""
from typing import List, Optional
from pydantic import BaseModel


class AskRequest(BaseModel):
    query: str
    top_k: int = 10
    max_turns: int = 4


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: List[str] = []
    tool_calls_used: int = 0
    ms: int = 0
    retrieval: Optional[dict] = None


class SearchHit(BaseModel):
    chunk_id: str
    doc_id: str
    score: float
    text: str


class DocumentOut(BaseModel):
    id: str
    filename: str
    bytes: int = 0
    sha_short: str = ""
    status: str = ""
    chunks: int = 0
    error: Optional[str] = None
    updated_at: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str
