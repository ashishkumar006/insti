"""Ingest orchestration with hashing dedup (existing data/ left alone)."""
import os
import threading
import uuid

from app.config import cfg
from app.pipeline import extract as ex, clean as cl, chunk as ch, hash as hx
from app.storage.db import get_conn
from app.storage.repositories import docs_repo as docs
from app.llm.factory import get_llm


def _job_log(job_id, msg):
    try:
        with get_conn() as conn:
            docs.append_log(conn, job_id, msg)
    except Exception:
        pass


def ingest_upload(staged_path: str, filename: str) -> dict:
    """Validate -> hash -> dedup -> background embed. Returns doc + job ids."""
    with open(staged_path, "rb") as f:
        raw_bytes = f.read()
    if len(raw_bytes) > cfg.max_upload_mb * 1024 * 1024:
        raise ValueError("File over {}MB limit".format(cfg.max_upload_mb))
    sha_raw = hx.sha256_bytes(raw_bytes)
    raw_text = ex.extract_text(staged_path, filename)
    cleaned = cl.clean_text(raw_text)
    if len(cleaned.strip()) < 20:
        raise ValueError("No extractable text found")
    sha_norm = hx.sha256_text(cleaned)

    with get_conn() as conn:
        existing = docs.find_by_sha_norm(conn, sha_norm)
        if existing:  # identical content -> no re-embed
            dup_id = docs.create_doc(conn, filename, sha_raw, _uniq(sha_norm), 0)
            docs.set_status(conn, dup_id, "duplicate", existing["chunks"])
            return {"doc_id": dup_id, "status": "duplicate",
                    "existing": existing["filename"], "job_id": None}
        doc_id = docs.create_doc(conn, filename, sha_raw, sha_norm, len(raw_bytes))
        items = [(i, hx.chunk_hash(sha_norm, i, t), t)
                 for i, t in enumerate(ch.chunk(cleaned, cfg.chunk_size, cfg.chunk_overlap))]
        docs.insert_chunk_placeholders(conn, doc_id, items)
        job_id = docs.create_job(conn, doc_id)
    t = threading.Thread(target=_embed_job, args=(doc_id, job_id), daemon=True)
    t.start()
    return {"doc_id": doc_id, "status": "indexing", "job_id": job_id}


def _uniq(sha_norm: str) -> str:
    # alias dup rows need unique sha_norm; suffix with random (dedup via lookup above)
    return (sha_norm[:56] + uuid.uuid4().hex[:8])


def _embed_job(doc_id: str, job_id: str):
    llm = get_llm()
    try:
        with get_conn() as conn:
            docs.set_status(conn, doc_id, "embedding")
            missing = docs.missing_embeddings(conn, doc_id)
        _job_log(job_id, "Embedding {} chunks...".format(len(missing)))
        with get_conn() as conn:
            docs.set_total(conn, job_id, len(missing))
            docs.set_done(conn, job_id, 0)
        done = 0
        for cid, idx, text in missing:
            vec = llm.embed(text[:8000])["embedding"]
            with get_conn() as conn:
                docs.set_embedding(conn, cid, vec)
            done += 1
            if done % 10 == 0 or done == len(missing):
                _job_log(job_id, "{}/{} embedded".format(done, len(missing)))
            with get_conn() as conn:
                docs.set_done(conn, job_id, done)
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM chunks WHERE doc_id=%s", (doc_id,))
            n = cur.fetchone()[0]
            docs.set_status(conn, doc_id, "indexed", n)
            docs.finish_job(conn, job_id, "done")
        _job_log(job_id, "Done: {} chunks indexed".format(n))
    except Exception as e:  # noqa
        try:
            with get_conn() as conn:
                docs.set_status(conn, doc_id, "failed", 0, str(e)[:500])
                docs.finish_job(conn, job_id, "error")
        except Exception:
            pass
        _job_log(job_id, "ERROR: {}".format(e))
