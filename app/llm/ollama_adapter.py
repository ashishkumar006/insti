"""Local Ollama adapter. Embeddings + chat, no gateway, no keys."""
from typing import Dict, List, Optional
import httpx

from app.config import cfg
from app.llm.base import LLMProvider


class OllamaAdapter(LLMProvider):
    supports_tools = False

    def __init__(self, base_url: str = "", embed_model: str = "", chat_model: str = ""):
        self.base_url = (base_url or cfg.ollama_url).rstrip("/")
        self.embed_model = embed_model or cfg.ollama_embed_model
        self.chat_model = chat_model or cfg.ollama_chat_model

    def _embed_one(self, text: str, task: str) -> Dict:
        prefix = "search_query: " if task == "retrieval_query" else "search_document: "
        with httpx.Client(timeout=120.0) as c:
            r = c.post(self.base_url + "/api/embeddings",
                       json={"model": self.embed_model, "prompt": prefix + text})
            r.raise_for_status()
            vec = (r.json().get("embedding") or [])
        if not vec:
            raise RuntimeError("ollama returned no embedding")
        return {"embedding": vec, "dim": len(vec)}

    def embed(self, text: str) -> Dict:
        return self._embed_one(text, "retrieval_document")

    def embed_query(self, text: str) -> Dict:
        return self._embed_one(text, "retrieval_query")

    def chat(self, messages: Optional[List[dict]] = None, system: Optional[str] = None,
             tools: Optional[list] = None, tool_choice: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.3,
             prompt: Optional[str] = None) -> Dict:
        msgs = list(messages or [])
        if prompt is not None:
            msgs.append({"role": "user", "content": prompt})
        if system:
            msgs = [{"role": "system", "content": system}] + msgs
        with httpx.Client(timeout=180.0) as c:
            r = c.post(self.base_url + "/api/chat", json={
                "model": self.chat_model, "messages": msgs, "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens}})
            r.raise_for_status()
            text = ((r.json().get("message") or {}).get("content") or "")
        return {"text": text, "tool_calls": []}
