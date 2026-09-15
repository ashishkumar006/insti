"""RRF fusion."""
from collections import defaultdict
from typing import Dict, List


def rrf_fuse(dense: List[dict], sparse: List[dict], k: int = 60,
             dense_w: float = 0.5, sparse_w: float = 0.5) -> List[dict]:
    scores: Dict[str, float] = defaultdict(float)
    texts: Dict[str, str] = {}
    meta: Dict[str, dict] = {}
    for rank, r in enumerate(dense):
        cid = r["chunk_id"]
        scores[cid] += dense_w * (1.0 / (k + rank + 1))
        texts[cid] = r.get("text", "")
        meta[cid] = {"doc_id": r.get("doc_id", ""), "chunk_id": cid}
    for rank, r in enumerate(sparse):
        cid = r["chunk_id"]
        scores[cid] += sparse_w * (1.0 / (k + rank + 1))
        texts.setdefault(cid, r.get("text", ""))
        meta.setdefault(cid, {"doc_id": r.get("doc_id", ""), "chunk_id": cid})
    out = [{"chunk_id": cid, "doc_id": meta[cid]["doc_id"],
            "score": round(s, 6), "text": texts.get(cid, "")}
           for cid, s in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    return out
