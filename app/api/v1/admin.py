"""Admin API: auth (accounts+passwords) + documents + jobs."""
import os
import shutil
import uuid
from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from app.config import cfg
from app.core.schemas import LoginRequest
from app.storage.db import get_conn
from app.storage.repositories import docs_repo as docs
from app.storage.repositories import users_repo as users
from app.services import ingest_service as ingest

router = APIRouter()


def require_admin(authorization: str = Header("")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Login required")
    data = users.read_token(authorization[7:])
    if not data:
        raise HTTPException(401, "Session expired")
    return data


@router.post("/auth/login")
def login(req: LoginRequest):
    with get_conn() as conn:
        users.ensure_seed_admin(conn)
        u = users.verify_login(conn, req.email.strip().lower(), req.password)
    if not u:
        raise HTTPException(401, "Invalid email or password")
    return {"token": users.make_token(u["id"], u["email"]), "email": u["email"]}


@router.get("/documents")
def list_docs(_=Depends(require_admin)):
    with get_conn() as conn:
        return {"documents": docs.list_docs(conn)}


@router.post("/documents/upload")
def upload(file: UploadFile = File(...), _=Depends(require_admin)):
    from app.pipeline.extract import SUPPORTED
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in SUPPORTED:
        raise HTTPException(400, "Unsupported file. Use: " + ", ".join(SUPPORTED))
    os.makedirs(cfg.storage_dir, exist_ok=True)
    staged = os.path.join(cfg.storage_dir, uuid.uuid4().hex + ext)
    with open(staged, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        return ingest.ingest_upload(staged, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/documents/{doc_id}/reindex")
def reindex(doc_id: str, _=Depends(require_admin)):
    from app.services.ingest_service import _embed_job
    import threading
    with get_conn() as conn:
        job_id = docs.create_job(conn, doc_id, "reindex")
    threading.Thread(target=_embed_job, args=(doc_id, job_id), daemon=True).start()
    return {"job_id": job_id, "status": "started"}


@router.delete("/documents/{doc_id}")
def delete(doc_id: str, _=Depends(require_admin)):
    with get_conn() as conn:
        docs.delete_doc(conn, doc_id)
    return {"status": "deleted"}


@router.get("/jobs/{job_id}")
def job(job_id: str, _=Depends(require_admin)):
    with get_conn() as conn:
        j = docs.get_job(conn, job_id)
    if not j:
        raise HTTPException(404, "job not found")
    return j
