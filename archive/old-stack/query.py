"""
query.py

Standalone script to ask questions against the pre-built retrieval index.

Flow:
  1. Loads the FAISS dense index + SQLite sparse index from disk
  2. Embeds the query via the real LLM gateway (nomic-embed-text / gemini)
  3. Runs dense (FAISS cosine) + sparse (BM25) retrieval
  4. Fuses results with RRF
  5. Passes top-k chunks to the LLM via the gateway with a fetch tool
  6. Prints the LLM's answer

Usage:
    # Make sure the index exists (run index_document.py first)
    python index_document.py test_data/sample_doc.txt --doc-id sample

    # Ask a question
    python query.py "What causes Amazon deforestation?"

    # Or with options
    python query.py "Tell me about indigenous communities" --top-k 5 --max-turns 3 --provider gemini

The LLM gateway must be running (default: http://localhost:8109).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from config import cfg
from gateway_client import GatewayClient
from vector_store import DenseStore
from sparse_store import SparseStore
from retriever import HybridRetriever
from agent import run_agent, FETCH_TOOL, SYSTEM_PROMPT


GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8109")


def load_index():
    dense_store = DenseStore(dim=768)
    sparse_store = SparseStore()
    if dense_store.count == 0:
        print("[ERROR] No dense index found.")
        print(f"        Run first: python index_document.py <your_file.txt>")
        sys.exit(1)
    gateway = GatewayClient(GATEWAY_URL, default_provider=cfg.llm_provider)
    retriever = HybridRetriever(dense_store, sparse_store, gateway)
    return retriever


def show_chunks():
    chunks_path = os.path.join(cfg.index_dir, "chunks.json")
    if not os.path.exists(chunks_path):
        print(f"[ERROR] chunks.json not found at {chunks_path}")
        sys.exit(1)
    with open(chunks_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    chunks = data.get("chunks", [])
    print(f"\n[CHUNKS] {len(chunks)} chunks in {data.get('doc_id', 'unknown')}")
    print("=" * 70)
    for c in chunks:
        print(f"\n[{c['chunk_id']}] ({c['char_count']} chars)")
        print(c["text"][:300] + ("..." if len(c["text"]) > 300 else ""))


def ask_query(query, top_k=10, max_turns=4, provider=None):
    retriever = load_index()
    gateway = retriever.embedder

    print(f"\n[QUERY] {query!r}")
    print(f"[QUERY] top_k={top_k}, max_turns={max_turns}, provider={provider or 'default'}")
    print()

    result = run_agent(
        query=query,
        retriever=retriever,
        gateway=gateway,
        max_turns=max_turns,
        provider=provider,
    )

    print("=" * 70)
    print("ANSWER:")
    print("=" * 70)
    print(result.answer)
    print()
    print(f"[SOURCES] {len(result.sources)} chunks used: {', '.join(result.sources[:5])}")
    print(f"[TOOL CALLS] {result.tool_calls_used}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Query the retrieval index with an LLM agent"
    )
    parser.add_argument("query", nargs="?", help="Question to ask")
    parser.add_argument("--top-k", type=int, default=10, help="Top-k chunks to retrieve")
    parser.add_argument("--max-turns", type=int, default=4, help="Max agent tool-call turns")
    parser.add_argument("--provider", default=None, help="LLM provider override (e.g. gemini, ollama)")
    parser.add_argument("--show-chunks", action="store_true", help="Show indexed chunks and exit")
    parser.add_argument("--gateway-url", default=GATEWAY_URL, help="LLM gateway URL")
    args = parser.parse_args()

    if args.show_chunks:
        show_chunks()
        sys.exit(0)

    if not args.query:
        parser.print_help()
        sys.exit(1)

    ask_query(
        query=args.query,
        top_k=args.top_k,
        max_turns=args.max_turns,
        provider=args.provider,
    )
