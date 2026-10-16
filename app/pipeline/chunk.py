"""Chunking: paragraph-aware, table-safe.

Design notes:
- Prose paragraphs are packed by sentence (up to chunk_size).
- Line-structured blocks (tables, menus, rosters, timetables - lines that do not
  end in sentence punctuation) are packed by LINE so rows stay together.
  Splitting a table mid-row destroys "what is for dinner on Wednesday".
- Chunk size defaults to ~350 tokens (~270 words): big enough for context,
  small enough that the embedding is topically focused.
- Overlap is word-based (chunk_overlap words of the previous chunk's tail).
"""
import re
from typing import List

_WORD_RE = re.compile(r"\S+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKENS_PER_WORD = 1.3


def _paras(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sents(p: str) -> List[str]:
    return [s.strip() for s in _SENT_SPLIT.split(p) if s.strip()]


def _toks(t: str) -> int:
    return max(1, int(len(_WORD_RE.findall(t)) * _TOKENS_PER_WORD))


def _looks_structured(block: str) -> bool:
    """True for tables/menus/rosters: many short lines, few sentence endings."""
    lines = [ln for ln in block.split("\n") if ln.strip()]
    if len(lines) < 3:
        return False
    prose_lines = sum(1 for ln in lines if ln.rstrip().endswith((".", "!", "?", ":")))
    return prose_lines <= len(lines) // 3


def _pack_sentences(sentences: List[str], chunk_size: int) -> List[str]:
    out: List[str] = []
    buf = ""
    for s in sentences:
        cand = (buf + " " + s).strip() if buf else s
        if _toks(cand) <= chunk_size:
            buf = cand
            continue
        if buf:
            out.append(buf)
        buf = s if _toks(s) <= chunk_size else ""
        while _toks(s) > chunk_size:  # single huge sentence: hard-split by words
            words = _WORD_RE.findall(s)
            step = max(1, int(chunk_size / _TOKENS_PER_WORD))
            out.append(" ".join(words[:step]))
            s = " ".join(words[step:])
            buf = s if _toks(s) <= chunk_size else buf
    if buf:
        out.append(buf)
    return out


def _pack_lines(lines: List[str], chunk_size: int) -> List[str]:
    out: List[str] = []
    buf_lines: List[str] = []
    for ln in lines:
        cand = "\n".join(buf_lines + [ln])
        if _toks(cand) <= chunk_size:
            buf_lines.append(ln)
            continue
        if buf_lines:
            out.append("\n".join(buf_lines))
        if _toks(ln) <= chunk_size:
            buf_lines = [ln]
        else:
            # one very long line: hard-split by words
            words = _WORD_RE.findall(ln)
            step = max(1, int(chunk_size / _TOKENS_PER_WORD))
            for j in range(0, len(words), step):
                piece = " ".join(words[j:j + step])
                if _toks(piece) <= chunk_size:
                    out.append(piece)
            buf_lines = []
    if buf_lines:
        out.append("\n".join(buf_lines))
    return out


def chunk(text: str, chunk_size: int = 350, chunk_overlap: int = 50) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        chunk_overlap = 0
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size // 4

    raw: List[str] = []
    for para in _paras(text):
        if _toks(para) <= chunk_size:
            raw.append(para)
            continue
        if _looks_structured(para):
            lines = [ln.rstrip() for ln in para.split("\n") if ln.strip()]
            raw.extend(_pack_lines(lines, chunk_size))
        else:
            raw.extend(_pack_sentences(_sents(para), chunk_size))

    if len(raw) <= 1:
        return raw

    overlap_words = max(0, int(chunk_overlap / _TOKENS_PER_WORD))
    out: List[str] = []
    for i, c in enumerate(raw):
        if i > 0 and overlap_words > 0:
            prev = _WORD_RE.findall(raw[i - 1])
            if 0 < len(prev) < overlap_words and not _looks_structured(raw[i - 1]):
                tail = raw[i - 1]
            elif _looks_structured(raw[i - 1]):
                tail = ""  # never glue a table tail onto the next block
            else:
                tail = " ".join(prev[-overlap_words:])
            c = (tail + " " + c).strip() if tail else c
        out.append(c.strip())
    return [c for c in out if c]
