"""Student API (open)."""
from fastapi import APIRouter
from app.config import cfg
from app.core.schemas import AskRequest, AskResponse
from app.services import query_service as qs

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    out = qs.ask(req.query, req.top_k or cfg.top_k, req.max_turns)
    return {"query": req.query, **out}


@router.get("/search")
def search(q: str, top_k: int = 10):
    return qs.search(q, top_k)
