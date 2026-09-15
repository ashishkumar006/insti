import os
import json
import numpy as np
import faiss
from typing import List, Dict, Optional

from app.config import cfg


class DenseStore:
    def __init__(self, dim: int = 768, index_path: Optional[str] = None):
        self.dim = dim
        self.index_path = index_path or os.path.join(cfg.index_dir, "dense.index")
        self.meta_path = os.path.join(cfg.index_dir, "dense_meta.json")
        self.id_map: List[str] = []
        self.text_map: Dict[str, str] = {}

        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
            if os.path.exists(self.meta_path):
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.id_map = data.get("ids", [])
                    self.text_map = {k: v for k, v in data.get("texts", {}).items()}
        else:
            self.index = faiss.IndexFlatIP(dim)

    def _normalize(self, vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms

    def add(self, chunk_id: str, embedding: List[float], text: str) -> None:
        vec = np.array([embedding], dtype=np.float32)
        vec = self._normalize(vec)
        self.index.add(vec)
        self.id_map.append(chunk_id)
        self.text_map[chunk_id] = text

    def search(self, query_embedding: List[float], top_k: int = 10) -> List[dict]:
        if self.index.ntotal == 0:
            return []
        vec = np.array([query_embedding], dtype=np.float32)
        vec = self._normalize(vec)
        scores, indices = self.index.search(vec, min(top_k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.id_map):
                continue
            cid = self.id_map[idx]
            results.append({"chunk_id": cid, "score": float(score), "text": self.text_map[cid]})
        return results

    def save(self) -> None:
        os.makedirs(cfg.index_dir, exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump({"ids": self.id_map, "texts": self.text_map}, f, ensure_ascii=False)

    @property
    def count(self) -> int:
        return self.index.ntotal
