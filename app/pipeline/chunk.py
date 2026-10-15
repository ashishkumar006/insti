"""Chunking (moved from ingest.py, same behavior)."""
import re
from typing import List


def _paras(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sents(p: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]


def _toks(t: str) -> int:
    return max(1, int(len(t.split()) * 1.3))


def chunk(text: str, chunk_size: int = 750, chunk_overlap: int = 75) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        chunk_overlap = 0
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size // 2
    raw: List[str] = []
    for para in _paras(text):
        if _toks(para) <= chunk_size:
            raw.append(para)
            continue
        buf = ""
        for s in _sents(para):
            cand = (buf + " " + s).strip() if buf else s
            if _toks(cand) <= chunk_size:
                buf = cand
            else:
                if buf:
                    raw.append(buf)
                if _toks(s) <= chunk_size:
                    buf = s
                else:
                    # long sentence: split by words into token-bounded pieces (no data lost)
                    words = s.split()
                    step = max(1, int(chunk_size / 1.3))
                    for j in range(0, len(words), step):
                        piece = " ".join(words[j : j + step])
                        if piece.strip():
                            raw.append(piece.strip())
                    buf = ""
        if buf:
            raw.append(buf)
    if len(raw) <= 1:
        return raw
    # token-based overlap (words, not chars) — 1.3 tok ≈ 1 word for speed
    overlap_words = max(0, int(chunk_overlap / 1.3))
    out: List[str] = []
    for i, c in enumerate(raw):
        if i > 0 and overlap_words > 0:
            prev_words = raw[i - 1].split()
            tail = " ".join(prev_words[-overlap_words:]) if overlap_words < len(prev_words) else raw[i - 1]
            c = tail + " " + c
        out.append(c.strip())
    return out
