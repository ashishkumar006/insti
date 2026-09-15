"""Sparse search via Postgres full-text."""
from typing import List


def sparse_search(conn, query: str, top_k: int = 30) -> List[dict]:
    cur = conn.cursor()
    cur.execute(
        """SELECT d.filename AS doc_id,
                  (d.filename || '::chunk_' || LPAD(c.idx::text,5,'0')) AS chunk_id,
                  c.text, ts_rank(c.text_tsv, plainto_tsquery('english', %s)) AS score
           FROM chunks c JOIN documents d ON d.id=c.doc_id
           WHERE c.text_tsv @@ plainto_tsquery('english', %s) AND d.status='indexed'
           ORDER BY score DESC LIMIT %s""",
        (query, query, top_k),
    )
    return [{"doc_id": r[0], "chunk_id": r[1], "text": r[2], "score": float(r[3])}
            for r in cur.fetchall()]
