"""Student API (open)."""
import os
import json
import datetime
from fastapi import APIRouter
from app.config import cfg
from app.core.schemas import AskRequest, AskResponse, FeedbackRequest
from app.services import query_service as qs

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    out = qs.ask(req.query, req.top_k or cfg.top_k)
    return {"query": req.query, **out}


@router.get("/search")
def search(q: str, top_k: int = 10):
    return qs.search(q, top_k)


@router.post("/feedback")
def feedback(req: FeedbackRequest):
    """Store query/answer/helpful for later improvement (file + best-effort DB)."""
    entry = {
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "query": req.query[:2000],
        "answer": req.answer[:8000],
        "helpful": bool(req.helpful),
        "ms": int(req.ms or 0),
    }
    # file: var/feedback.jsonl (gitignored via var/)
    try:
        os.makedirs("var", exist_ok=True)
        with open("var/feedback.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # also try DB query_logs helpful column if exists (ignore if not)
    try:
        from app.storage.db import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO feedback(query,answer,helpful,ms) VALUES(%s,%s,%s,%s)", (entry["query"], entry["answer"], entry["helpful"], entry["ms"]))
    except Exception:
        pass
    return {"status": "ok"}
