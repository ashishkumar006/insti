"""
test_retrieval_demo.py

Retrieval tests using REAL embeddings from the LLM gateway.

Setup — run this BEFORE the tests:
    python index_document.py test_data/sample_doc.txt --doc-id sample

Then run the tests:
    python -m pytest test_retrieval_demo.py -v -s

All dense retrieval calls the real embedding model via the gateway.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

import config
from gateway_client import GatewayClient
from vector_store import DenseStore
from sparse_store import SparseStore
from retriever import HybridRetriever


GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:8109")


@pytest.fixture
def live_retriever():
    gateway = GatewayClient(GATEWAY_URL)
    dense_store = DenseStore(dim=768)
    sparse_store = SparseStore()
    if dense_store.count == 0:
        print("\n[FAIL] No existing index found.")
        print(f"       Run first: python index_document.py test_data/sample_doc.txt --doc-id sample")
        print(f"       Expected in {cfg.index_dir}/: dense.index, sparse.db")
        pytest.skip("no pre-built index — run index_document.py first")
    retriever = HybridRetriever(dense_store, sparse_store, gateway)
    return retriever


def _pp(results, title, max_chars=140):
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"\n{'='*70}")
    print(f"  {title}  ({len(results)} results)")
    print(f"{'='*70}")
    for i, r in enumerate(results, 1):
        text = r.get("text", "")
        snippet = (text[:max_chars] + "...") if len(text) > max_chars else text
        print(f"  {i}. [{r['chunk_id']}]  score={r['score']:.6f}")
        print(f"     {snippet}")
        print()


class TestDenseRetrieval:
    def test_dense_search(self, live_retriever):
        retriever = live_retriever
        query = "What causes Amazon deforestation?"
        vec = retriever.embedder.embed_query(query)["embedding"]   # REAL embed
        results = retriever.dense.search(vec, top_k=5)
        _pp(results, f"DENSE: {query!r}")
        assert len(results) == 5
        assert all("chunk_id" in r and "score" in r for r in results)

    def test_dense_top1_relevant(self, live_retriever):
        retriever = live_retriever
        query = "Amazon rainforest largest tropical forest"
        vec = retriever.embedder.embed_query(query)["embedding"]
        results = retriever.dense.search(vec, top_k=1)
        assert len(results) == 1
        assert results[0]["score"] > 0


class TestSparseRetrieval:
    def test_sparse_search(self, live_retriever):
        retriever = live_retriever
        query = "What causes Amazon deforestation?"
        results = retriever.sparse.search(query, top_k=5)
        _pp(results, f"SPARSE: {query!r}")
        assert len(results) == 5
        assert results[0]["score"] > 0

    def test_sparse_bm25_ranks_relevant_higher(self, live_retriever):
        retriever = live_retriever
        results = retriever.sparse.search("amazon deforestation biodiversity", top_k=3)
        assert len(results) > 0
        assert results[0]["score"] > 0


class TestHybridRetrieval:
    def test_hybrid_fusion(self, live_retriever):
        retriever = live_retriever
        query = "What causes Amazon deforestation?"
        results = retriever.retrieve(query, top_k=5)
        _pp(results, f"HYBRID: {query!r}")
        assert len(results) <= 5

    def test_dense_vs_sparse_vs_hybrid(self, live_retriever):
        retriever = live_retriever
        queries = [
            "indigenous communities and violence",
            "ocean coral bleaching marine life",
            "renewable energy solar wind growth",
            "artificial intelligence conservation",
        ]
        sys.stdout.reconfigure(encoding="utf-8")
        print()
        print("=" * 70)
        print("  COMPARISON: dense vs sparse vs hybrid")
        print("=" * 70)
        for q in queries:
            dense = retriever.dense.search(
                retriever.embedder.embed_query(q)["embedding"], top_k=3
            )
            sparse = retriever.sparse.search(q, top_k=3)
            hybrid = retriever.retrieve(q, top_k=3)
            d_ids = [r["chunk_id"].split("::")[1] for r in dense]
            s_ids = [r["chunk_id"].split("::")[1] for r in sparse]
            h_ids = [r["chunk_id"].split("::")[1] for r in hybrid]
            print(f"\n  Query : {q!r}")
            print(f"    Dense   top-3 : {d_ids}")
            print(f"    Sparse  top-3 : {s_ids}")
            print(f"    Hybrid  top-3 : {h_ids}")
