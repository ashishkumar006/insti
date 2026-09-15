"""System API."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    out = {"api": "ok", "postgres": "unknown", "llm": "unknown"}
    try:
        from app.storage.db import get_conn
        with get_conn() as conn:
            conn.cursor().execute("SELECT 1")
        out["postgres"] = "ok"
    except Exception as e:  # noqa
        out["postgres"] = "down: {}".format(e)[:120]
    try:
        from app.config import cfg
        out["llm"] = "{}:{}".format(cfg.llm_mode, cfg.gateway_url if cfg.llm_mode == "gateway" else cfg.paygo_chat_model)
    except Exception:
        pass
    return out


@router.get("/stats")
def stats():
    """Public corpus stats for the student UI trust signal. Never fails."""
    out = {"documents": 0, "chunks": 0}
    try:
        from app.storage.db import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*), COALESCE(SUM(chunks),0) FROM documents WHERE status='indexed'")
            r = cur.fetchone()
            out["documents"] = (r[0] or 0) if r else 0
            out["chunks"] = (r[1] or 0) if r else 0
    except Exception:  # noqa - degraded mode shows zeros
        pass
    return out
