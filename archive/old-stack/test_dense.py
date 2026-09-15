import tempfile
import os
import numpy as np
from unittest.mock import patch, MagicMock

import pytest

import config
from vector_store import DenseStore
from gateway_client import GatewayClient
from sparse_store import SparseStore, _tokenize, _normalize


@pytest.fixture
def isolated_cfg():
    with tempfile.TemporaryDirectory() as td:
        old_dir = config.cfg.index_dir
        config.cfg.index_dir = td
        yield td
        config.cfg.index_dir = old_dir


class TestDenseStore:
    def test_empty_index_search_returns_empty(self, isolated_cfg):
        store = DenseStore(dim=768)
        results = store.search([0.0] * 768)
        assert results == []

    def test_add_and_search_top1(self, isolated_cfg):
        store = DenseStore(dim=768)
        store.add("chunk_0", [1.0] * 768, "text about cats")
        store.add("chunk_1", [-1.0] * 768, "text about dogs")
        results = store.search([1.0] * 768, top_k=1)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk_0"
        assert results[0]["text"] == "text about cats"

    def test_search_top_k_limits_results(self, isolated_cfg):
        store = DenseStore(dim=768)
        for i in range(20):
            vec = np.zeros(768, dtype=np.float32)
            vec[i % 2] = 1.0
            store.add(f"chunk_{i}", vec.tolist(), f"text {i}")
        results = store.search([1.0, 0.0] * 384, top_k=5)
        assert len(results) <= 5

    def test_cosine_similarity_ranking(self, isolated_cfg):
        store = DenseStore(dim=768)
        arr = np.eye(768, dtype=np.float32)
        # col 0 → identity-like (high overlap with [1,0,0...])
        # col 1 → different direction (low overlap)
        vec_high = arr[0].tolist()
        vec_low  = arr[1].tolist()
        store.add("high", vec_high, "high sim")
        store.add("low",  vec_low,  "low sim")
        query = [1.0] + [0.0] * 767
        results = store.search(query, top_k=2)
        assert results[0]["chunk_id"] == "high"
        assert results[0]["score"] > results[1]["score"]

    def test_id_and_text_maps_populated(self, isolated_cfg):
        store = DenseStore(dim=768)
        store.add("a", [1.0] * 768, "first")
        store.add("b", [1.0] * 768, "second")
        assert store.id_map == ["a", "b"]
        assert store.text_map["a"] == "first"
        assert store.text_map["b"] == "second"

    def test_count_property(self, isolated_cfg):
        store = DenseStore(dim=768)
        assert store.count == 0
        store.add("x", [1.0] * 768, "doc")
        assert store.count == 1


class TestGatewayClientEmbed:
    @patch("gateway_client.httpx.Client")
    def test_embed_returns_768_vector(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "embedding": [0.1] * 768,
            "dim": 768,
            "latency_ms": 10,
            "attempted": [],
        }
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = mock_resp

        client = GatewayClient("http://localhost:9999")
        resp = client.embed("some document text")
        assert len(resp["embedding"]) == 768
        assert resp["dim"] == 768
        assert resp["provider"] == "ollama"

    @patch("gateway_client.httpx.Client")
    def test_embed_query_uses_retrieval_query_task(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "embedding": [0.1] * 768,
            "dim": 768,
            "latency_ms": 10,
            "attempted": [],
        }
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = mock_resp

        client = GatewayClient("http://localhost:9999")
        client.embed_query("search query")
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["task_type"] == "retrieval_query"

    @patch("gateway_client.httpx.Client")
    def test_embed_sends_retrieval_document_task(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "provider": "ollama",
            "model": "nomic-embed-text",
            "embedding": [0.1] * 768,
            "dim": 768,
            "latency_ms": 10,
            "attempted": [],
        }
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = mock_resp

        client = GatewayClient("http://localhost:9999")
        client.embed("doc text")
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["task_type"] == "retrieval_document"


class TestEndToEndDense:
    @patch("gateway_client.httpx.Client")
    def test_query_ranks_closest_document(self, mock_client_cls, isolated_cfg):
        vec_cats = np.zeros(768, dtype=np.float32); vec_cats[0] = 1.0
        vec_dogs = np.zeros(768, dtype=np.float32); vec_dogs[1] = 1.0
        vec_cars = np.zeros(768, dtype=np.float32); vec_cars[2] = 1.0

        def fake_embed(text, provider=None):
            if "cats" in text:
                return {"embedding": vec_cats.tolist(), "dim": 768, "provider": "x", "model": "m", "latency_ms": 0, "attempted": []}
            if "dogs" in text:
                return {"embedding": vec_dogs.tolist(), "dim": 768, "provider": "x", "model": "m", "latency_ms": 0, "attempted": []}
            return {"embedding": vec_cars.tolist(), "dim": 768, "provider": "x", "model": "m", "latency_ms": 0, "attempted": []}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = fake_embed
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = mock_resp

        store = DenseStore(dim=768)
        for cid, vec in [("doc_cats", vec_cats), ("doc_dogs", vec_dogs), ("doc_cars", vec_cars)]:
            store.add(cid, vec.tolist(), f"document about {cid}")

        results = store.search(vec_cats.tolist(), top_k=2)
        assert results[0]["chunk_id"] == "doc_cats"
        assert results[1]["chunk_id"] in {"doc_dogs", "doc_cars"}
        assert results[0]["score"] > results[1]["score"]
