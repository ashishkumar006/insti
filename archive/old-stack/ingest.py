import re
from typing import List


def _split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_sentences(paragraph: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", paragraph)
    return [p.strip() for p in parts if p.strip()]


def _hard_cut(text: str, limit: int) -> List[str]:
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def _token_count(text: str) -> int:
    return max(1, int(len(text.split()) * 1.25))


def chunk(text: str, chunk_size: int = 750, chunk_overlap: int = 75) -> List[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        chunk_overlap = 0
    if chunk_overlap >= chunk_size:
        chunk_overlap = chunk_size // 2

    paragraphs = _split_paragraphs(text)
    raw_chunks: List[str] = []

    for para in paragraphs:
        if _token_count(para) <= chunk_size:
            raw_chunks.append(para)
            continue

        sentences = _split_sentences(para)
        buf = ""
        for sent in sentences:
            candidate = (buf + " " + sent).strip() if buf else sent
            if _token_count(candidate) <= chunk_size:
                buf = candidate
            else:
                if buf:
                    raw_chunks.append(buf)
                if _token_count(sent) > chunk_size:
                    raw_chunks.extend(_hard_cut(sent, chunk_size * 4))
                    buf = ""
                else:
                    buf = sent

        if buf:
            raw_chunks.append(buf)

    if len(raw_chunks) <= 1:
        return raw_chunks

    overlapped: List[str] = []
    for i, chunk in enumerate(raw_chunks):
        if i > 0 and chunk_overlap > 0:
            tail = raw_chunks[i - 1][-chunk_overlap:]
            chunk = tail + " " + chunk
        overlapped.append(chunk.strip())

    return overlapped
