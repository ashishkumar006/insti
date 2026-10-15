"""Local Ollama adapter: chat fallback for offline dev.

Embeddings are Gemini-only (see direct_adapter.py), so this adapter
intentionally has no embed methods.
"""
from typing import Dict, List, Optional
import httpx

from app.config import cfg
from app.llm.base import LLMProvider


class OllamaAdapter(LLMProvider):
    supports_tools = False

    def __init__(self, base_url: str = "", chat_model: str = ""):
        self.base_url = (base_url or cfg.ollama_url).rstrip("/")
        self.chat_model = chat_model or cfg.ollama_chat_model

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
