"""Document / chunk / job repositories (thin SQL)."""


DOC_COLS = ["id", "filename", "sha_raw", "sha_norm", "status", "bytes", "chunks", "error"]


def _row(cur, cols):
    r = cur.fetchone()
    return dict(zip(cols, r)) if r else None


def find_by_sha_norm(conn, sha_norm):
    cur = conn.cursor()
    cur.execute("SELECT {} FROM documents WHERE sha_norm=%s".format(",".join(DOC_COLS)), (sha_norm,))
    return _row(cur, DOC_COLS)


def create_doc(conn, filename, sha_raw, sha_norm, nbytes):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO documents(filename,sha_raw,sha_norm,status,bytes)
           VALUES(%s,%s,%s,'uploaded',%s) RETURNING id""",
        (filename, sha_raw, sha_norm, nbytes),
    )
    return str(cur.fetchone()[0])


def set_status(conn, doc_id, status, chunks=0, error=None):
    cur = conn.cursor()
    cur.execute("UPDATE documents SET status=%s,chunks=%s,error=%s,updated_at=now() WHERE id=%s",
                (status, chunks, error, doc_id))


def list_docs(conn):
    cur = conn.cursor()
    cur.execute("""SELECT id,filename,bytes,sha_norm,status,chunks,error,
                          to_char(updated_at,'YYYY-MM-DD HH24:MI') FROM documents
                   ORDER BY updated_at DESC""")
    out = []
    for r in cur.fetchall():
        out.append({"id": str(r[0]), "filename": r[1], "bytes": r[2],
                    "sha_short": (r[3] or "")[:10], "status": r[4],
                    "chunks": r[5], "error": r[6], "updated_at": r[7]})
    return out


def insert_chunk_placeholders(conn, doc_id, items):
    """items: [(idx, chunk_hash, text)]. ON CONFLICT keeps existing embedding."""
    cur = conn.cursor()
    for idx, chash, text in items:
        cur.execute(
            """INSERT INTO chunks(doc_id,idx,chunk_hash,text,chars)
               VALUES(%s,%s,%s,%s,%s) ON CONFLICT (chunk_hash) DO NOTHING""",
            (doc_id, idx, chash, text, len(text)),
        )


def missing_embeddings(conn, doc_id):
    cur = conn.cursor()
    cur.execute("SELECT id,idx,text FROM chunks WHERE doc_id=%s AND embedding IS NULL ORDER BY idx",
                (doc_id,))
    return cur.fetchall()


def set_embedding(conn, chunk_id, vec):
    from app.retrieval.dense_pg import _vec_literal
    cur = conn.cursor()
    cur.execute("UPDATE chunks SET embedding=%s::vector WHERE id=%s",
                (_vec_literal(list(vec)), str(chunk_id)))


def delete_doc(conn, doc_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM documents WHERE id=%s", (doc_id,))


def create_job(conn, doc_id, kind="ingest"):
    cur = conn.cursor()
    cur.execute("INSERT INTO jobs(doc_id,kind) VALUES(%s,%s) RETURNING id", (doc_id, kind))
    return str(cur.fetchone()[0])


def append_log(conn, job_id, msg):
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET log=array_append(log,%s),updated_at=now() WHERE id=%s", (msg, job_id))


def finish_job(conn, job_id, status):
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET status=%s,updated_at=now() WHERE id=%s", (status, job_id))


def set_total(conn, job_id, total):
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET total=%s,updated_at=now() WHERE id=%s", (total, job_id))


def set_done(conn, job_id, done):
    cur = conn.cursor()
    cur.execute("UPDATE jobs SET done=%s,updated_at=now() WHERE id=%s", (done, job_id))


def get_job(conn, job_id):
    cur = conn.cursor()
    cur.execute("SELECT id,doc_id,kind,status,log,total,done FROM jobs WHERE id=%s", (job_id,))
    r = cur.fetchone()
    if not r:
        return None
    return {"id": str(r[0]), "doc_id": str(r[1]) if r[1] else None,
            "kind": r[2], "status": r[3], "log": r[4] or [],
            "total": r[5] or 0, "done": r[6] or 0}
