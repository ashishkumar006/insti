"""
main.py — Retrieval Agent server + CLI.

Usage:
  python main.py serve [--port 8200]   start web dashboard
  python main.py ingest <path>         index a document via CLI
  python main.py ask <query>           ask a question via CLI

Dashboard (default: http://localhost:8200):
  - Lists documents in data/ with green/red indexing status
  - Index button per document with live log output
  - Search box for querying indexed documents
"""
import argparse
import asyncio
import json
import os
import sys
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Optional, Dict, List, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from starlette.staticfiles import StaticFiles
from pydantic import BaseModel

from config import cfg
from ingest import chunk
from gateway_client import GatewayClient
from vector_store import DenseStore
from sparse_store import SparseStore
from retriever import HybridRetriever
from agent import run_agent, AgentResult


# ── Paths ──────────────────────────────────────────────────────────────────────

DATA_DIR = Path(cfg.data_dir)
INDEX_DIR = Path(cfg.index_dir)

# ── In-memory job + log state (resets on restart) ─────────────────────────────

_jobs: Dict[str, dict] = {}
_logs: deque = deque(maxlen=2000)
_log_seq = 0


def _log(level: str, message: str, job_id: Optional[str] = None):
    global _log_seq
    _log_seq += 1
    _logs.append({
        "seq": _log_seq, "ts": time.time(), "level": level,
        "message": message, "job_id": job_id,
    })


# ── Request / Response models ──────────────────────────────────────────────────

class IngestRequest(BaseModel):
    text: str
    doc_id: str = "default"
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


class IngestResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    dense_count: int


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 10


class RetrieveResponse(BaseModel):
    query: str
    results: list
    sources: list


class AskRequest(BaseModel):
    query: str
    top_k: int = 10
    max_turns: int = 4
    provider: Optional[str] = None


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list
    tool_calls_used: int


class StatusResponse(BaseModel):
    dense_count: int
    sparse_count: int
    gateway_url: str


# ── App + lifecycle ────────────────────────────────────────────────────────────

app = FastAPI(title="Retrieval Agent")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
app.mount("/frontend", StaticFiles(directory=str(Path(__file__).parent / "frontend"), html=True), name="frontend")
gateway: Optional[GatewayClient] = None
retriever: Optional[HybridRetriever] = None


@app.on_event("startup")
def startup():
    global gateway, retriever
    gateway = GatewayClient(cfg.gateway_url, default_provider=cfg.llm_provider, embed_provider=cfg.embed_provider)
    ds = DenseStore(dim=768)
    ss = SparseStore()
    retriever = HybridRetriever(ds, ss, gateway)
    _log("info", f"Server started · gateway={cfg.gateway_url} · index_dir={cfg.index_dir}")
    print(f"[SERVER] Gateway : {cfg.gateway_url}")
    print(f"[SERVER] Index   : {cfg.index_dir}")
    print(f"[SERVER] Data    : {cfg.data_dir}")


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# ── Document management API ────────────────────────────────────────────────────

@app.get("/api/documents")
def list_documents():
    """List every .txt file in data/ with indexing status and chunk count."""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Build doc_id -> chunk_count map from chunks.json
    chunk_counts: Dict[str, int] = {}
    chunks_json = INDEX_DIR / "chunks.json"
    if chunks_json.exists():
        try:
            data = json.loads(chunks_json.read_text(encoding="utf-8"))
            for c in data.get("chunks", []):
                doc_id = c["chunk_id"].split("::")[0]
                chunk_counts[doc_id] = chunk_counts.get(doc_id, 0) + 1
        except Exception:
            pass

    documents = []
    for f in sorted(DATA_DIR.iterdir()):
        if not f.is_file() or f.suffix.lower() != ".txt":
            continue
        name = f.name
        doc_id = f.name
        is_indexing = name in _jobs and _jobs[name].get("status") == "running"
        chunk_count = chunk_counts.get(doc_id, 0)
        documents.append({
            "name": name,
            "doc_id": doc_id,
            "size": f.stat().st_size,
            "size_human": f"{f.stat().st_size:,} bytes",
            "indexed": chunk_count > 0,
            "indexing": is_indexing,
            "chunks": chunk_count,
        })

    return {
        "documents": documents,
        "gateway_url": cfg.gateway_url,
        "index_dir": cfg.index_dir,
    }


@app.post("/api/index/{filename}")
def start_index_document(filename: str):
    """Kick off chunking + embedding for a data/ .txt file. Runs in background."""
    filepath = DATA_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(404, f"File not found: {filename}")
    if filepath.suffix.lower() != ".txt":
        raise HTTPException(400, "Only .txt files are supported")

    job_id = uuid.uuid4().hex[:12]
    _jobs[filename] = {
        "job_id": job_id,
        "status": "running",
        "started": time.time(),
        "filename": filename,
    }
    _log("info", f"Indexing started: {filename} (job={job_id})")

    t = threading.Thread(target=_run_index_job, args=(filename, job_id), daemon=True)
    t.start()

    return {"job_id": job_id, "filename": filename, "status": "started"}


@app.post("/api/index/{filename}/delete")
def delete_document_index(filename: str):
    """Delete indexed chunks for a specific document from the retrieval index."""
    filepath = DATA_DIR / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(404, f"File not found: {filename}")
    if filepath.suffix.lower() != ".txt":
        raise HTTPException(400, "Only .txt files are supported")

    doc_id = filename
    deleted_chunks = 0

    # Update chunks.json
    chunks_json = INDEX_DIR / "chunks.json"
    if chunks_json.exists():
        try:
            data = json.loads(chunks_json.read_text(encoding="utf-8"))
            original_count = len(data.get("chunks", []))
            data["chunks"] = [c for c in data.get("chunks", []) if not c.get("chunk_id", "").startswith(f"{doc_id}::")]
            deleted_chunks = original_count - len(data["chunks"])
            chunks_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            raise HTTPException(500, f"Failed to update chunks.json: {e}")

    # Update dense index
    dense_meta_path = INDEX_DIR / "dense_meta.json"
    dense_index_path = INDEX_DIR / "dense.index"
    if dense_meta_path.exists() and dense_index_path.exists():
        try:
            with open(dense_meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            
            ids = meta.get("ids", [])
            texts = meta.get("texts", {})
            keep_ids = [cid for cid in ids if not cid.startswith(f"{doc_id}::")]
            keep_texts = {cid: txt for cid, txt in texts.items() if not cid.startswith(f"{doc_id}::")}
            deleted_from_dense = len(ids) - len(keep_ids)
            
            if deleted_from_dense > 0:
                # Rebuild FAISS index with remaining vectors
                import numpy as np
                import faiss
                
                old_index = faiss.read_index(str(dense_index_path))
                remaining_vectors = []
                for i, cid in enumerate(ids):
                    if cid in keep_ids:
                        # Reconstruct vector from index
                        vec = old_index.reconstruct(i)
                        remaining_vectors.append(vec)
                
                if remaining_vectors:
                    new_index = faiss.IndexFlatIP(768)
                    vectors_array = np.array(remaining_vectors, dtype=np.float32)
                    new_index.add(vectors_array)
                    faiss.write_index(new_index, str(dense_index_path))
                    
                    meta["ids"] = keep_ids
                    meta["texts"] = keep_texts
                    with open(dense_meta_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)
                else:
                    # No vectors left, create empty index
                    new_index = faiss.IndexFlatIP(768)
                    faiss.write_index(new_index, str(dense_index_path))
                    meta["ids"] = []
                    meta["texts"] = {}
                    with open(dense_meta_path, "w", encoding="utf-8") as f:
                        json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise HTTPException(500, f"Failed to update dense index: {e}")

    # Update sparse index
    sparse_db_path = INDEX_DIR / "sparse.db"
    if sparse_db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(sparse_db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("DELETE FROM terms WHERE chunk_id LIKE ?", (f"{doc_id}::%",))
            terms_deleted = cursor.rowcount
            conn.execute("DELETE FROM chunk_texts WHERE chunk_id LIKE ?", (f"{doc_id}::%",))
            conn.commit()
            conn.close()
        except Exception as e:
            raise HTTPException(500, f"Failed to update sparse index: {e}")

    _log("info", f"Deleted {deleted_chunks} chunks for {filename}")
    return {
        "status": "deleted",
        "filename": filename,
        "deleted_chunks": deleted_chunks,
    }


@app.post("/api/cancel/{filename}")
def cancel_indexing(filename: str):
    if filename not in _jobs or _jobs[filename].get("status") != "running":
        raise HTTPException(404, "No active indexing job for this file")
    _jobs[filename]["status"] = "cancelled"
    _log("warn", f"Indexing cancelled by user: {filename}")
    return {"status": "cancelled", "filename": filename}


@app.get("/api/logs")
def get_logs(job_id: Optional[str] = None, since: int = 0):
    """Incremental log stream. Client polls this."""
    results = []
    for entry in _logs:
        if entry["seq"] <= since:
            continue
        if job_id and entry.get("job_id") != job_id:
            continue
        results.append({
            "seq": entry["seq"],
            "level": entry["level"],
            "message": entry["message"],
            "ts": entry["ts"],
            "job_id": entry.get("job_id"),
        })

    last_seq = results[-1]["seq"] if results else since
    done = False
    error = None

    if job_id:
        for name, info in _jobs.items():
            if info.get("job_id") == job_id:
                st = info.get("status")
                if st in ("done", "error", "cancelled"):
                    done = True
                    error = info.get("error")
                break

    return {"logs": results, "last_seq": last_seq, "done": done, "error": error, "job_id": job_id}


# ── Retrieval API ──────────────────────────────────────────────────────────────

@app.post("/ingest")
def api_ingest(req: IngestRequest):
    """Index raw text. Used by CLI and direct callers."""
    global retriever
    cs = req.chunk_size or cfg.chunk_size
    co = req.chunk_overlap or cfg.chunk_overlap
    chunks = chunk(req.text, chunk_size=cs, chunk_overlap=co)

    dense_store = retriever.dense
    sparse_store = retriever.sparse

    for i, c in enumerate(chunks):
        cid = f"{req.doc_id}::chunk_{i:05d}"
        result = gateway.embed(c)
        dense_store.add(cid, result["embedding"], c)
        sparse_store.add(cid, c)

    dense_store.save()
    sparse_store.save()
    retriever.dense = dense_store
    retriever.sparse = sparse_store

    _save_chunks_json(req.doc_id, chunks)
    _log("info", f"Ingested {len(chunks)} chunks for doc_id={req.doc_id}")
    return IngestResponse(doc_id=req.doc_id, chunks_indexed=len(chunks), dense_count=dense_store.count)


@app.post("/retrieve")
def retrieve(req: RetrieveRequest):
    if retriever is None:
        raise HTTPException(500, "retriever not initialised")
    results = retriever.retrieve(req.query, top_k=req.top_k)
    return RetrieveResponse(
        query=req.query,
        results=results,
        sources=[r["chunk_id"] for r in results],
    )


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if retriever is None:
        raise HTTPException(500, "retriever not initialised")
    try:
        result: AgentResult = run_agent(
            query=req.query,
            retriever=retriever,
            gateway=gateway,
            max_turns=req.max_turns,
            provider=req.provider,
        )
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return AskResponse(
        query=req.query,
        answer=result.answer,
        sources=result.sources,
        tool_calls_used=result.tool_calls_used,
    )


@app.get("/status", response_model=StatusResponse)
def status():
    if retriever is None:
        raise HTTPException(500, "retriever not initialised")
    return StatusResponse(
        dense_count=retriever.dense.count,
        sparse_count=retriever.sparse._N,
        gateway_url=cfg.gateway_url,
    )


# ── Background index job ────────────────────────────────────────────────────────

def _run_index_job(filename: str, job_id: str):
    """Run chunk + embed + store in a background thread."""
    global retriever
    _jobs[filename]["status"] = "running"
    try:
        filepath = DATA_DIR / filename
        _log("info", f"Reading {filename} ({filepath.stat().st_size:,} bytes)...", job_id=job_id)
        text = filepath.read_text(encoding="utf-8")

        cs = cfg.chunk_size
        co = cfg.chunk_overlap
        _log("info", f"Chunking {filename} (chunk_size={cs}, overlap={co})...", job_id=job_id)
        chunks = chunk(text, chunk_size=cs, chunk_overlap=co)
        _log("info", f"Produced {len(chunks)} chunks. Starting embedding...", job_id=job_id)

        dense_store = retriever.dense
        sparse_store = retriever.sparse

        for i, c in enumerate(chunks):
            if _jobs.get(filename, {}).get("status") == "cancelled":
                _log("warn", f"Indexing cancelled at chunk {i+1}/{len(chunks)}", job_id=job_id)
                _jobs[filename]["status"] = "cancelled"
                return

            cid = f"{filename}::chunk_{i:05d}"
            _log("info", f"[{i+1}/{len(chunks)}] Embedding {cid}...", job_id=job_id)
            resp = gateway.embed(c)
            dense_store.add(cid, resp["embedding"], c)
            sparse_store.add(cid, c)

        dense_store.save()
        sparse_store.save()
        retriever.dense = dense_store
        retriever.sparse = sparse_store

        _save_chunks_json(filename, chunks)

        _jobs[filename]["status"] = "done"
        _log("ok", f"Indexing complete: {filename} ({len(chunks)} chunks)", job_id=job_id)
    except Exception as e:
        _jobs[filename]["status"] = "error"
        _jobs[filename]["error"] = str(e)
        _log("err", f"Error indexing {filename}: {e}", job_id=job_id)


def _save_chunks_json(doc_id: str, chunks: list):
    path = INDEX_DIR / "chunks.json"
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    merged = {c["chunk_id"]: c for c in existing.get("chunks", []) if "::" in c.get("chunk_id", "")}
    for i, c in enumerate(chunks):
        merged[f"{doc_id}::chunk_{i:05d}"] = {"chunk_id": f"{doc_id}::chunk_{i:05d}", "text": c, "char_count": len(c)}
    existing["chunks"] = list(merged.values())
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _cli_ingest(path: str, doc_id: str):
    import httpx
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    port = os.getenv("RETRIEVAL_PORT", "8200")
    r = httpx.post(f"http://localhost:{port}/ingest", json={"text": text, "doc_id": doc_id}, timeout=300)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


def _cli_ask(query: str, top_k: int = 10, provider: Optional[str] = None):
    import httpx
    port = os.getenv("RETRIEVAL_PORT", "8200")
    payload = {"query": query, "top_k": top_k}
    if provider:
        payload["provider"] = provider
    r = httpx.post(f"http://localhost:{port}/ask", json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    print(f"Q: {query}")
    print(f"A: {data['answer']}")
    print(f"Sources ({len(data['sources'])}): {', '.join(data['sources'][:5])}")
    print(f"Tool calls: {data['tool_calls_used']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retrieval Agent")
    sub = parser.add_subparsers(dest="cmd")

    p_ingest = sub.add_parser("ingest", help="Index a text file")
    p_ingest.add_argument("path")
    p_ingest.add_argument("--doc-id", default="default")

    p_ask = sub.add_parser("ask", help="Ask a question")
    p_ask.add_argument("query")
    p_ask.add_argument("--top-k", type=int, default=10)
    p_ask.add_argument("--provider", default=None)

    p_serve = sub.add_parser("serve", help="Run dashboard + API server")
    p_serve.add_argument("--port", type=int, default=int(os.getenv("RETRIEVAL_PORT", "8200")))
    p_serve.add_argument("--reload", action="store_true")

    args = parser.parse_args()

    if args.cmd == "ingest":
        _cli_ingest(args.path, args.doc_id)
    elif args.cmd == "ask":
        _cli_ask(args.query, args.top_k, args.provider)
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=args.port, reload=args.reload)
    else:
        parser.print_help()
        sys.exit(1)
