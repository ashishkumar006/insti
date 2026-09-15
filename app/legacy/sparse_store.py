import math
import sqlite3
import os
from collections import Counter
from typing import List, Dict, Optional

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer

from app.config import cfg


_stop_words = set(stopwords.words("english"))
_stemmer = PorterStemmer()


def _tokenize(text: str) -> List[str]:
    tokens = [t.lower() for t in __import__("re").findall(r"\w+", text) if t]
    return [t for t in tokens if t not in _stop_words]


def _normalize(tokens: List[str]) -> List[str]:
    return [_stemmer.stem(t) for t in tokens]


class SparseStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(cfg.index_dir, "sparse.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self._df: Dict[str, int] = {}
        self._N: int = 0
        self._avg_dl: float = 0.0
        self._load_stats()

    def _init_db(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS terms (
                term TEXT,
                chunk_id TEXT,
                tf INTEGER,
                PRIMARY KEY (term, chunk_id)
            )
            """
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS chunk_texts (chunk_id TEXT PRIMARY KEY, text TEXT)"
        )
        self.conn.commit()

    def _load_stats(self):
        row = self.conn.execute("SELECT v FROM meta WHERE k='N'").fetchone()
        if row:
            self._N = int(row["v"])
        row = self.conn.execute("SELECT v FROM meta WHERE k='avg_dl'").fetchone()
        if row:
            self._avg_dl = float(row["v"])
        rows = self.conn.execute(
            "SELECT term, COUNT(DISTINCT chunk_id) as df FROM terms GROUP BY term"
        ).fetchall()
        self._df = {r["term"]: r["df"] for r in rows}

    def add(self, chunk_id: str, text: str) -> None:
        tokens = _tokenize(text)
        stems = _normalize(tokens)
        tf = Counter(stems)
        dl = len(stems)
        rows = [(term, chunk_id, count) for term, count in tf.items()]
        self.conn.executemany(
            "INSERT OR REPLACE INTO terms (term, chunk_id, tf) VALUES (?,?,?)", rows
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO chunk_texts (chunk_id, text) VALUES (?,?)",
            (chunk_id, text),
        )
        self._N += 1
        self._avg_dl = (
            (self._avg_dl * (self._N - 1) + dl) / self._N if self._N > 0 else float(dl)
        )
        for term in tf:
            self._df[term] = self._df.get(term, 0) + 1
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (k, v) VALUES (?,?)", ("N", str(self._N))
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (k, v) VALUES (?,?)", ("avg_dl", str(self._avg_dl))
        )
        self.conn.commit()

    def _bm25_score(self, term: str, tf: int, dl: int) -> float:
        k1, b = 1.5, 0.75
        df = self._df.get(term, 0)
        if df == 0 or self._N == 0:
            return 0.0
        idf = math.log((self._N - df + 0.5) / (df + 0.5) + 1.0)
        tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(self._avg_dl, 1e-6)))
        return idf * tf_norm

    def search(self, query: str, top_k: int = 10) -> List[dict]:
        if self._N == 0:
            return []
        tokens = _tokenize(query)
        stems = _normalize(tokens)
        if not stems:
            return []
        placeholders = ",".join("?" * len(stems))
        rows = self.conn.execute(
            f"""
            SELECT t.chunk_id, t.term, t.tf
            FROM terms t
            WHERE t.term IN ({placeholders})
            """,
            stems,
        ).fetchall()

        scores: Dict[str, float] = {}
        for row in rows:
            cid = row["chunk_id"]
            term = row["term"]
            tf = row["tf"]
            total_tf = self.conn.execute(
                "SELECT SUM(tf) as s FROM terms WHERE chunk_id=?", (cid,)
            ).fetchone()
            dl = total_tf["s"] if total_tf and total_tf["s"] else 0
            scores[cid] = scores.get(cid, 0.0) + self._bm25_score(term, tf, dl)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for cid, score in ranked:
            txt = self.conn.execute(
                "SELECT text FROM chunk_texts WHERE chunk_id=?", (cid,)
            ).fetchone()
            results.append(
                {"chunk_id": cid, "score": float(score), "text": txt["text"] if txt else ""}
            )
        return results

    def add_chunk_text(self, chunk_id: str, text: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO chunk_texts (chunk_id, text) VALUES (?,?)",
            (chunk_id, text),
        )
        self.conn.commit()

    def save(self):
        self.conn.commit()

    def close(self):
        self.save()
        self.conn.close()
