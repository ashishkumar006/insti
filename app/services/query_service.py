"""Student query path: Postgres hybrid retrieval + grounded Gemini answer."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import cfg
from app.llm.factory import get_llm


def _grounded_answer(query: str, hits: list, llm) -> str:
    parts = ["[{}]\n{}".format(h["chunk_id"], h["text"]) for h in hits[:6]]
    ctx = "\n\n---\n\n".join(parts) if parts else "(no matching chunks found)"
    system = ("You are a helpful IIT Madras campus assistant. "
              "Answer ONLY from the document chunks below. "
              "If they lack the answer, say so honestly. "
              "Cite chunk ids inline like [chunk_id]. Keep answers concise and warm.")
    resp = llm.chat(messages=[{"role": "user", "content": "Question: " + query +
                               "\n\nDocument chunks:\n" + ctx}],
                    system=system, max_tokens=1024, temperature=0.3)
    return resp.get("text", "")


def _hits(llm, query: str, top_k: int):
    from app.retrieval.retriever import PgHybridRetriever
    hits, dbg = PgHybridRetriever(llm).retrieve_debug(query, top_k=top_k)
    dbg["backend"] = "postgres"
    return hits, dbg


def ask(query: str, top_k: int = 10) -> dict:
    t0 = time.time()
    llm = get_llm()
    hits, dbg = _hits(llm, query, top_k or cfg.top_k)
    answer = _grounded_answer(query, hits, llm)
    sources = [h["chunk_id"] for h in hits]
    ms = int((time.time() - t0) * 1000)
    try:
        from app.storage.db import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            import json
            cur.execute("INSERT INTO query_logs(query,answer,sources,ms) VALUES(%s,%s,%s,%s)",
                        (query, answer, json.dumps(sources[:20]), ms))
    except Exception:
        pass
    return {"answer": answer, "sources": sources, "tool_calls_used": 0, "ms": ms,
            "retrieval": dbg}


def search(query: str, top_k: int = 10) -> dict:
    llm = get_llm()
    hits, dbg = _hits(llm, query, top_k or cfg.top_k)
    return {"query": query, "results": hits, "retrieval": dbg}
