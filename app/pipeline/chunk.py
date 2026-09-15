"""Chunking (moved from ingest.py, same behavior)."""
import re
from typing import List


def _paras(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sents(p: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", p) if s.strip()]


def _toks(t: str) -> int:
    return max(1, int(len(t.split()) * 1.25))


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
                buf = "" if _toks(s) > chunk_size else s
                if _toks(s) > chunk_size:
                    raw.append(s[: chunk_size * 4])
        if buf:
            raw.append(buf)
    if len(raw) <= 1:
        return raw
    out: List[str] = []
    for i, c in enumerate(raw):
        if i > 0 and chunk_overlap > 0:
            c = raw[i - 1][-chunk_overlap:] + " " + c
        out.append(c.strip())
    return out
