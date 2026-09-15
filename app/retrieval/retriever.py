"""Postgres-backed hybrid retriever."""
import time
from app.config import cfg
from app.storage.db import get_conn
from app.retrieval import dense_pg, sparse_pg
from app.retrieval.hybrid import rrf_fuse


class PgHybridRetriever:
    def __init__(self, llm):
        self.llm = llm

    def retrieve(self, query: str, top_k: int = 10):
        hits, _ = self.retrieve_debug(query, top_k)
        return hits

    def retrieve_debug(self, query: str, top_k: int = 10):
        """Same as retrieve() plus per-stage evidence for diagnostics."""
        n = min(cfg.fusion_k, top_k * 3)
        t0 = time.time()
        with get_conn() as conn:
            try:
                qvec = self.llm.embed_query(query)["embedding"]
                embed_ms = int((time.time() - t0) * 1000)
                t1 = time.time()
                dense = dense_pg.dense_search(conn, qvec, n)
                dense_ms = int((time.time() - t1) * 1000)
            except Exception:
                dense, embed_ms, dense_ms = [], 0, 0
            t2 = time.time()
            sparse = sparse_pg.sparse_search(conn, query, n)
            sparse_ms = int((time.time() - t2) * 1000)
        fused = rrf_fuse(dense, sparse, cfg.fusion_k, cfg.dense_weight, cfg.sparse_weight)[:top_k]
        debug = {"dense_hits": len(dense), "sparse_hits": len(sparse),
                 "embed_ms": embed_ms, "dense_ms": dense_ms, "sparse_ms": sparse_ms}
        return fused, debug
