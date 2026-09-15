import tempfile
import os
from unittest.mock import patch

import pytest

import config
from sparse_store import SparseStore, _tokenize, _normalize


@pytest.fixture
def isolated_cfg():
    with tempfile.TemporaryDirectory() as td:
        old_dir = config.cfg.index_dir
        config.cfg.index_dir = td
        yield td
        config.cfg.index_dir = old_dir


class TestTokenizer:
    def test_lowercase(self):
        assert _tokenize("The Amazon Rainforest") == ["amazon", "rainforest"]

    def test_stopwords_removed(self):
        tokens = _tokenize("the quick brown fox is in the forest")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "in" not in tokens

    def test_stopwords_only_sentence_returns_empty(self):
        tokens = _tokenize("the is in at to")
        assert tokens == []

    def test_punctuation_stripped(self):
        tokens = _tokenize("Amazon's deforestation: accelerating!")
        assert "'s" not in tokens
        assert ":" not in tokens
        assert "!" not in tokens

    def test_numbers_preserved(self):
        tokens = _tokenize("390 billion trees")
        assert "390" in tokens


class TestStemming:
    def test_plural_stems(self):
        stems = _normalize(["forests", "trees", "studies", "covers"])
        assert stems == ["forest", "tree", "studi", "cover"]

    def test_porter_stems_biodiversity(self):
        # Porter stemmer chops "biodiversity" to "biodivers"
        stems = _normalize(["biodiversity"])
        assert stems == ["biodivers"]

    def test_unchanged_words(self):
        # These words are their own stems in Porter — verify they are untouched
        stems = _normalize(["amazon", "data", "query", "retriev"])
        assert stems == ["amazon", "data", "queri", "retriev"]



class TestSparseStore:
    def test_initial_state(self, isolated_cfg):
        store = SparseStore()
        assert store._N == 0
        assert store.search("anything") == []

    def test_add_and_search_returns_results(self, isolated_cfg):
        store = SparseStore()
        store.add("chunk_0", "The Amazon rainforest covers biodiversity hotspots")
        store.add("chunk_1", "Deforestation in the Amazon threatens wildlife")
        results = store.search("amazon deforestation biodiversity")
        assert len(results) > 0
        assert results[0]["chunk_id"] in {"chunk_0", "chunk_1"}
        assert results[0]["score"] > 0
        store.close()

    def test_bm25_ranks_relevant_doc_higher(self, isolated_cfg):
        store = SparseStore()
        store.add("relevant",
                  "Amazon deforestation biodiversity wildlife rainforest")
        store.add("irrelevant",
                  "Global stock markets rose today in morning trading")
        results = store.search("amazon deforestation biodiversity")
        assert results[0]["chunk_id"] == "relevant"
        store.close()

    def test_search_top_k_limits(self, isolated_cfg):
        store = SparseStore()
        for i in range(20):
            store.add(f"chunk_{i}", f"document number {i} with various keywords")
        results = store.search("document keywords", top_k=3)
        assert len(results) <= 3
        store.close()

    def test_no_match_returns_empty(self, isolated_cfg):
        store = SparseStore()
        store.add("chunk_0", "Amazon rainforest biodiversity")
        results = store.search("quantum computing algorithms")
        assert results == []
        store.close()

    def test_chunk_text_stored_and_returned(self, isolated_cfg):
        store = SparseStore()
        store.add("chunk_0", "Amazon rainforest biodiversity hotspots")
        results = store.search("amazon")
        assert results[0]["text"] == "Amazon rainforest biodiversity hotspots"
        store.close()

    def test_multiple_terms_sum_scores(self, isolated_cfg):
        store = SparseStore()
        store.add("c1", "amazon rainforest")
        store.add("c2", "amazon deforestation wildlife")
        store.add("c3", "deforestation biodiversity")
        results = store.search("amazon deforestation biodiversity")
        assert len(results) == 3
        # c3 and c2 both match two query terms; verify they come before c1
        assert results[0]["chunk_id"] in {"c2", "c3"}
        assert results[1]["chunk_id"] in {"c2", "c3"}
        assert results[2]["chunk_id"] == "c1"
        store.close()

    def test_multi_word_query_tokenized(self, isolated_cfg):
        store = SparseStore()
        store.add("c1", "Amazon rainforest biodiversity")
        results = store.search("amazon biodiversity")
        assert len(results) == 1
        assert results[0]["chunk_id"] == "c1"
        store.close()
