from typing import List, Dict, Optional
from collections import defaultdict

from app.config import cfg


def _rrf_fuse(
    dense_results: List[dict],
    sparse_results: List[dict],
    k: int = 60,
    dense_w: float = 0.5,
    sparse_w: float = 0.5,
) -> List[dict]:
    scores: Dict[str, float] = defaultdict(float)
    texts: Dict[str, str] = {}

    for rank, r in enumerate(dense_results):
        cid = r["chunk_id"]
        scores[cid] += dense_w * (1.0 / (k + rank + 1))
        texts[cid] = r.get("text", "")

    for rank, r in enumerate(sparse_results):
        cid = r["chunk_id"]
        scores[cid] += sparse_w * (1.0 / (k + rank + 1))
        if cid not in texts:
            texts[cid] = r.get("text", "")

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    out = []
    for cid, score in ranked:
        out.append({"chunk_id": cid, "score": round(score, 6), "text": texts.get(cid, "")})
    return out


class HybridRetriever:
    def __init__(self, dense_store, sparse_store, embedder):
        self.dense = dense_store
        self.sparse = sparse_store
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = 10) -> List[dict]:
        hits, _ = self.retrieve_debug(query, top_k)
        return hits

    def retrieve_debug(self, query: str, top_k: int = 10):
        import time
        t0 = time.time()
        try:
            qvec = self.embedder.embed_query(query)["embedding"]
            embed_ms = int((time.time() - t0) * 1000)
            t1 = time.time()
            dense_res = self.dense.search(qvec, top_k=min(cfg.fusion_k, top_k * 3))
            dense_ms = int((time.time() - t1) * 1000)
        except Exception:
            dense_res, embed_ms, dense_ms = [], 0, 0
        t2 = time.time()
        sparse_res = self.sparse.search(query, top_k=min(cfg.fusion_k, top_k * 3))
        sparse_ms = int((time.time() - t2) * 1000)
        fused = _rrf_fuse(
            dense_res, sparse_res,
            k=cfg.fusion_k,
            dense_w=cfg.dense_weight,
            sparse_w=cfg.sparse_weight,
        )[:top_k]
        debug = {"dense_hits": len(dense_res), "sparse_hits": len(sparse_res),
                 "embed_ms": embed_ms, "dense_ms": dense_ms, "sparse_ms": sparse_ms}
        return fused, debug
