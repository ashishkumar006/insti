"""Gemini pay-go adapter. REST only, key stays server-side, never logged."""
from typing import Dict, List, Optional
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

    def _embed_one(self, text: str, task: str) -> Dict:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/{}"
               ":embedContent".format(self.embed_model))
        body = {"model": "models/" + self.embed_model,
                "content": {"parts": [{"text": text}]},
                "taskType": "RETRIEVAL_QUERY" if task == "retrieval_query" else "RETRIEVAL_DOCUMENT",
                "outputDimensionality": cfg.embed_dim}
        with httpx.Client(timeout=120.0) as c:
            r = c.post(url, json=body, params={"key": self.api_key})
            if r.status_code != 200:
                raise RuntimeError("gemini embed failed: {}".format(r.status_code))
            vec = ((r.json().get("embedding") or {}).get("values") or [])
        if not vec:
            raise RuntimeError("gemini returned no embedding")
        return {"embedding": vec, "dim": len(vec)}

    def embed(self, text: str) -> Dict:
        return self._embed_one(text, "retrieval_document")

    def embed_query(self, text: str) -> Dict:
        return self._embed_one(text, "retrieval_query")

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
