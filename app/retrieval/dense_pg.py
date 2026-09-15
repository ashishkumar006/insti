"""Dense search via pgvector cosine."""
from typing import List


def _vec_literal(vec: List[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


def dense_search(conn, query_vec: List[float], top_k: int = 30) -> List[dict]:
    lit = _vec_literal(query_vec)
    cur = conn.cursor()
    cur.execute(
        """SELECT d.filename AS doc_id,
                  (d.filename || '::chunk_' || LPAD(c.idx::text,5,'0')) AS chunk_id,
                  c.text, 1 - (c.embedding <=> %s::vector) AS score
           FROM chunks c JOIN documents d ON d.id=c.doc_id
           WHERE c.embedding IS NOT NULL AND d.status='indexed'
           ORDER BY c.embedding <=> %s::vector LIMIT %s""",
        (lit, lit, top_k),
    )
    rows = cur.fetchall()
    return [{"doc_id": r[0], "chunk_id": r[1], "text": r[2], "score": float(r[3])} for r in rows]
