"""Dense search via pgvector cosine."""
from typing import List

from app.config import cfg


def _vec_literal(vec: List[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def dense_search(conn, query_vec: List[float], top_k: int = 30) -> List[dict]:
    lit = _vec_literal(query_vec)
    cur = conn.cursor()
    # Only chunks embedded with the CURRENT model: vectors from a different
    # model are in an incompatible space. NULL (pre-004 rows) stays searchable.
    cur.execute(
        """SELECT d.filename AS doc_id,
                  (d.filename || '::chunk_' || LPAD(c.idx::text,5,'0')) AS chunk_id,
                  c.text, 1 - (c.embedding <=> %s::vector) AS score
           FROM chunks c JOIN documents d ON d.id=c.doc_id
           WHERE c.embedding IS NOT NULL AND d.status='indexed'
             AND (c.embed_model IS NULL OR c.embed_model=%s)
           ORDER BY c.embedding <=> %s::vector LIMIT %s""",
        (lit, cfg.paygo_embed_model, lit, top_k),
    )
    rows = cur.fetchall()
    return [{"doc_id": r[0], "chunk_id": r[1], "text": r[2], "score": float(r[3])} for r in rows]
