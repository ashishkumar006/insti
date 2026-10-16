"""Gemini pay-go adapter. REST only, key stays server-side, never logged."""
from typing import Dict, List, Optional
import time
import httpx

from app.config import cfg
from app.llm.base import LLMProvider


class GeminiAdapter(LLMProvider):
    supports_tools = False

    def __init__(self, api_key: str = "", chat_model: str = "", embed_model: str = ""):
        if not api_key:
            raise RuntimeError("Gemini API key missing")
        self.api_key = api_key
        self.chat_model = chat_model or cfg.paygo_chat_model
        self.embed_model = embed_model or cfg.paygo_embed_model

    def _embed_one(self, text: str, task: str, title: str = "") -> Dict:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/{}"
               ":embedContent".format(self.embed_model))
        body = {"model": "models/" + self.embed_model,
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_QUERY" if task == "retrieval_query" else "RETRIEVAL_DOCUMENT",
                "outputDimensionality": cfg.embed_dim}
        if title:
            body["title"] = title[:500]
        with httpx.Client(timeout=120.0) as c:
            r = c.post(url, json=body, params={"key": self.api_key})
            if r.status_code != 200:
                raise RuntimeError("gemini embed failed: {}".format(r.status_code))
            vec = ((r.json().get("embedding") or {}).get("values") or [])
        if not vec:
            raise RuntimeError("gemini returned no embedding")
        return {"embedding": vec, "dim": len(vec)}

    def embed(self, text: str, title: str = "") -> Dict:
        return self._embed_one(text, "retrieval_document", title)

    def embed_image(self, data: bytes, mime: str = "image/png", title: str = "") -> Dict:
        """Embed a raw image (multimodal models only, e.g. gemini-embedding-2)."""
        return self._embed_media_one(data, mime, "retrieval_document", title)

    def _embed_media_one(self, data: bytes, mime: str, task: str, title: str = "") -> Dict:
        import base64
        url = ("https://generativelanguage.googleapis.com/v1beta/models/{}"
               ":embedContent".format(self.embed_model))
        body = {"model": "models/" + self.embed_model,
                "content": {"parts": [{"inline_data": {"mime_type": mime,
                                                       "data": base64.b64encode(data).decode()}}]},
                "taskType": "RETRIEVAL_QUERY" if task == "retrieval_query" else "RETRIEVAL_DOCUMENT",
                "outputDimensionality": cfg.embed_dim}
        if title:
            body["title"] = title[:500]
        with httpx.Client(timeout=120.0) as c:
            r = c.post(url, json=body, params={"key": self.api_key})
            if r.status_code != 200:
                raise RuntimeError("gemini embed failed: {}".format(r.status_code))
            vec = ((r.json().get("embedding") or {}).get("values") or [])
        if not vec:
            raise RuntimeError("gemini returned no embedding")
        return {"embedding": vec, "dim": len(vec)
                }

    def embed_query(self, text: str) -> Dict:
        return self._embed_one(text, "retrieval_query")

    def _post_retry(self, client: httpx.Client, url: str, body: dict,
                    attempts: int = 6) -> dict:
        """POST with patient backoff on 429/5xx; honors Retry-After.

        Free-tier embedding quotas are per-minute windows, so a burst needs to
        wait ~a minute: exponential backoff 2s -> ~100s with jitter.
        """
        import random
        delay = 2.0
        status = None
        for n in range(attempts):
            r = client.post(url, json=body, params={"key": self.api_key})
            if r.status_code == 200:
                return r.json()
            status = r.status_code
            if status not in (429, 500, 502, 503, 504):
                break
            if n < attempts - 1:
                try:
                    wait = max(delay, float(r.headers.get("retry-after") or 0))
                except ValueError:
                    wait = delay
                wait = min(wait * (1 + random.random() * 0.25), 120.0)
                time.sleep(wait)
                delay *= 3
        raise RuntimeError("gemini call failed: {}".format(status))

    def embed_batch(self, texts: List[str], title: str = "") -> List[List[float]]:
        """Batch embed documents via batchEmbedContents (up to 100 per request)."""
        if not texts:
            return []
        size = max(1, min(100, cfg.embed_batch_size))
        url = ("https://generativelanguage.googleapis.com/v1beta/models/{}"
               ":batchEmbedContents".format(self.embed_model))
        out: List[List[float]] = []
        req: dict = {}
        if title:
            req["title"] = title[:500]
        with httpx.Client(timeout=120.0) as c:
            for i in range(0, len(texts), size):
                reqs = [dict({"model": "models/" + self.embed_model,
                              "content": {"parts": [{"text": t}]},
                              "taskType": "RETRIEVAL_DOCUMENT",
                              "outputDimensionality": cfg.embed_dim}, **req)
                        for t in texts[i:i + size]]
                data = self._post_retry(c, url, {"requests": reqs})
                embs = data.get("embeddings") or []
                if len(embs) != len(reqs):
                    raise RuntimeError("gemini batch returned {} embeddings for {} inputs"
                                       .format(len(embs), len(reqs)))
                for e in embs:
                    vec = e.get("values") or []
                    if not vec:
                        raise RuntimeError("gemini returned no embedding")
                    out.append(vec)
        return out

    def embed_images_batch(self, items: List[tuple], title: str = "") -> List[List[float]]:
        """Batch embed images: items = [(bytes, mime), ...]."""
        if not items:
            return []
        import base64
        size = max(1, min(100, cfg.embed_batch_size))
        url = ("https://generativelanguage.googleapis.com/v1beta/models/{}"
               ":batchEmbedContents".format(self.embed_model))
        out: List[List[float]] = []
        req: dict = {}
        if title:
            req["title"] = title[:500]
        with httpx.Client(timeout=120.0) as c:
            for i in range(0, len(items), size):
                reqs = [dict({"model": "models/" + self.embed_model,
                              "content": {"parts": [{"inline_data": {
                                  "mime_type": mime,
                                  "data": base64.b64encode(data).decode()}}]},
                              "taskType": "RETRIEVAL_DOCUMENT",
                              "outputDimensionality": cfg.embed_dim}, **req)
                        for data, mime in items[i:i + size]]
                data = self._post_retry(c, url, {"requests": reqs})
                embs = data.get("embeddings") or []
                if len(embs) != len(reqs):
                    raise RuntimeError("gemini batch returned {} embeddings for {} inputs"
                                       .format(len(embs), len(reqs)))
                for e in embs:
                    vec = e.get("values") or []
                    if not vec:
                        raise RuntimeError("gemini returned no embedding")
                    out.append(vec)
        return out

    def chat(self, messages: Optional[List[dict]] = None, system: Optional[str] = None,
             tools: Optional[list] = None, tool_choice: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.3,
             prompt: Optional[str] = None) -> Dict:
        parts_text = []
        for m in (messages or []):
            content = m.get("content", "")
            if isinstance(content, list):
                content = "\n".join([b.get("text", "") for b in content if isinstance(b, dict)])
            parts_text.append("{}: {}".format(m.get("role", "user"), content))
        if prompt is not None:
            parts_text.append("user: " + prompt)
        url = ("https://generativelanguage.googleapis.com/v1beta/models/{}"
               ":generateContent".format(self.chat_model))
        body = {"contents": [{"role": "user", "parts": [{"text": "\n".join(parts_text)}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}}
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        with httpx.Client(timeout=180.0) as c:
            r = c.post(url, json=body, params={"key": self.api_key})
            if r.status_code != 200:
                raise RuntimeError("gemini chat failed: {}".format(r.status_code))
            cands = r.json().get("candidates") or []
        text = ""
        if cands:
            text = "".join([p.get("text", "") for p in
                            ((cands[0].get("content") or {}).get("parts") or [])])
        return {"text": text, "tool_calls": []}

    def ocr_image(self, png_bytes: bytes,
                  prompt: str = "Transcribe this document page as markdown. "
                                "Preserve headings, lists and tables.") -> str:
        """Vision OCR for scanned pages. Needs no local services."""
        import base64
        url = ("https://generativelanguage.googleapis.com/v1beta/models/{}"
               ":generateContent".format(self.chat_model))
        body = {"contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inline_data": {"mime_type": "image/png",
                             "data": base64.b64encode(png_bytes).decode()}}]}],
                "generationConfig": {"maxOutputTokens": 4096, "temperature": 0.0}}
        with httpx.Client(timeout=180.0) as c:
            r = c.post(url, json=body, params={"key": self.api_key})
            if r.status_code != 200:
                raise RuntimeError("gemini ocr failed: {}".format(r.status_code))
            cands = r.json().get("candidates") or []
        if not cands:
            return ""
        return "".join([p.get("text", "") for p in
                        ((cands[0].get("content") or {}).get("parts") or [])])
