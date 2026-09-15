"""SHA-256 helpers for file + chunk dedup."""
import hashlib


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_text(text: str) -> str:
    import re
    import unicodedata
    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace("\r\n", "\n").replace("\r", "\n").strip()
    t = re.sub(r"[ \t]+", " ", t)
    while "\n\n\n" in t:
        t = t.replace("\n\n\n", "\n\n")
    return t.strip().lower()


def sha256_text(text: str) -> str:
    return sha256_bytes(normalize_text(text).encode("utf-8"))


def chunk_hash(doc_sha_norm: str, idx: int, text: str) -> str:
    return sha256_bytes("{}::{}::{}".format(doc_sha_norm, idx, text).encode("utf-8"))


def short(sha: str, n: int = 10) -> str:
    return (sha or "")[:n]
