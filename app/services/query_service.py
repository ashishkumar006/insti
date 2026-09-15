"""Student query path: gateway -> agent w/ tools; direct -> local index + grounded answer."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import cfg
from app.agent.runner import run_agent
from app.llm.factory import get_llm


def _local_retriever(llm):
    from app.legacy.vector_store import DenseStore
    from app.legacy.sparse_store import SparseStore
    from app.legacy.retriever import HybridRetriever
    return HybridRetriever(DenseStore(dim=cfg.embed_dim), SparseStore(), llm)


def _direct_answer(query: str, hits: list, llm) -> str:
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


def _direct_hits(llm, query: str, top_k: int):
    # Postgres first (admin uploads), local file index as fallback.
    try:
        from app.retrieval.retriever import PgHybridRetriever
        hits, dbg = PgHybridRetriever(llm).retrieve_debug(query, top_k=top_k)
        dbg["backend"] = "postgres"
        if hits:
            return hits, dbg
    except Exception:
        pass
    hits, dbg = _local_retriever(llm).retrieve_debug(query, top_k=top_k)
    dbg["backend"] = "local-files"
    return hits, dbg


def ask(query: str, top_k: int = 10, max_turns: int = 4) -> dict:
    t0 = time.time()
    llm = get_llm()
    if cfg.llm_mode == "gateway":
        from app.retrieval.retriever import PgHybridRetriever
        res = run_agent(query, PgHybridRetriever(llm), llm, max_turns=max_turns)
        answer, sources, calls = res.answer, res.sources, res.tool_calls_used
        dbg = {"backend": "postgres-agent", "dense_hits": len(sources), "sparse_hits": -1,
               "embed_ms": -1, "dense_ms": -1, "sparse_ms": -1}
    else:
        hits, dbg = _direct_hits(llm, query, top_k or cfg.top_k)
        answer = _direct_answer(query, hits, llm)
        sources, calls = [h["chunk_id"] for h in hits], 0
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
    return {"answer": answer, "sources": sources, "tool_calls_used": calls, "ms": ms,
            "retrieval": dbg}


def search(query: str, top_k: int = 10) -> dict:
    llm = get_llm()
    if cfg.llm_mode == "gateway":
        from app.retrieval.retriever import PgHybridRetriever
        hits, dbg = PgHybridRetriever(llm).retrieve_debug(query, top_k or cfg.top_k)
    else:
        hits, dbg = _direct_hits(llm, query, top_k or cfg.top_k)
    return {"query": query, "results": hits, "retrieval": dbg}
