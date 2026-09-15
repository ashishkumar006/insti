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
