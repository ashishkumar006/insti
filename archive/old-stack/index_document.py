"""
index_document.py

Standalone script to index a text document for retrieval:

  1. Reads a .txt file
  2. Chunks it into overlapping passages
  3. Embeds each chunk via the LLM gateway (real embedding model)
  4. Stores vectors in FAISS + BM25 terms in SQLite
  5. Saves a human-readable JSON of chunks under indexes/
  6. Saves everything to disk under indexes/

Usage:
    python index_document.py path/to/document.txt [--doc-id mydoc] [--chunk-size 500] [--overlap 50]

After running this, you can query the index with query.py or the API server.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from config import cfg
from ingest import chunk
from gateway_client import GatewayClient
from vector_store import DenseStore
from sparse_store import SparseStore


def index_document(
    text: str,
    doc_id: str = "default",
    chunk_size: int = 500,
    overlap: int = 50,
    gateway_url: str = "http://localhost:8109",
):
    gateway = GatewayClient(gateway_url, default_provider=cfg.llm_provider)
    chunks = chunk(text, chunk_size=chunk_size, overlap=overlap)

    dense_store = DenseStore(dim=768)
    sparse_store = SparseStore()

    print(f"[INDEX] Chunking: {len(chunks)} chunks")
    t0 = time.time()
    for i, c in enumerate(chunks):
        cid = f"{doc_id}::chunk_{i:05d}"
        print(f"[INDEX] Embedding chunk {i+1}/{len(chunks)} ...", end="\r")
        resp = gateway.embed(c)                  # REAL call to embedding model
        dense_store.add(cid, resp["embedding"], c)
        sparse_store.add(cid, c)

    dense_store.save()
    sparse_store.save()

    # Save human-readable JSON of chunks
    chunks_json_path = os.path.join(cfg.index_dir, "chunks.json")
    chunks_data = [
        {"chunk_id": f"{doc_id}::chunk_{i:05d}", "text": c, "char_count": len(c)}
        for i, c in enumerate(chunks)
    ]
    with open(chunks_json_path, "w", encoding="utf-8") as f:
        json.dump({"doc_id": doc_id, "chunks": chunks_data}, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    print(f"\n[INDEX] Done in {elapsed:.1f}s")
    print(f"[INDEX] Dense vectors : {dense_store.count}")
    print(f"[INDEX] Sparse docs   : {sparse_store._N}")
    print(f"[INDEX] Saved to      : {cfg.index_dir}/")
    print(f"   - {cfg.index_dir}/dense.index")
    print(f"   - {cfg.index_dir}/dense_meta.json")
    print(f"   - {cfg.index_dir}/sparse.db")
    print(f"   - {cfg.index_dir}/chunks.json  (human-readable)")
    return dense_store, sparse_store


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index a text document for retrieval")
    parser.add_argument("path", help="Path to .txt file")
    parser.add_argument("--doc-id", default="default", help="Document identifier")
    parser.add_argument("--chunk-size", type=int, default=500, help="Chunk size in characters")
    parser.add_argument("--overlap", type=int, default=50, help="Overlap between chunks")
    parser.add_argument("--gateway-url", default=os.getenv("GATEWAY_URL", "http://localhost:8109"),
                        help="LLM gateway URL")
    args = parser.parse_args()

    if not os.path.isfile(args.path):
        print(f"Error: file not found: {args.path}")
        sys.exit(1)

    with open(args.path, "r", encoding="utf-8") as fh:
        text = fh.read()

    print(f"[INDEX] File  : {args.path}")
    print(f"[INDEX] DocID : {args.doc_id}")
    print(f"[INDEX] Size  : {len(text):,} chars")
    print(f"[INDEX] Gateway: {args.gateway_url}")
    print()

    index_document(
        text=text,
        doc_id=args.doc_id,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        gateway_url=args.gateway_url,
    )
