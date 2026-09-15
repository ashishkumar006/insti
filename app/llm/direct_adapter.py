"""Direct adapter: Gemini API first when configured for cloud, else local Ollama.

Cloud (no localhost): EMBED_MODE=gemini -> Gemini embeddings + Gemini chat.
Local dev (default): Ollama embeddings (+ Gemini fallback), Gemini chat (+ Ollama fallback).
"""
from typing import Dict, List, Optional
from app.config import cfg
from app.llm.base import LLMProvider


class DirectAdapter(LLMProvider):
    supports_tools = False

    def __init__(self):
        from app.llm.ollama_adapter import OllamaAdapter
        from app.llm.gemini_adapter import GeminiAdapter
        self._ollama = OllamaAdapter()
        key = cfg.gemini_api_key or cfg.paygo_api_key
        self._gemini = GeminiAdapter(key) if key else None
        self._embed_mode = (cfg.embed_mode or "ollama").lower()

    def _gemini_or_raise(self):
        if self._gemini is None:
            raise RuntimeError("no Gemini key and Ollama failed")
        return self._gemini

    def embed(self, text: str) -> Dict:
        if self._embed_mode == "gemini":
            try:
                return self._gemini_or_raise().embed(text)
            except Exception:
                return self._ollama.embed(text)
        try:
            return self._ollama.embed(text)
        except Exception:
            return self._gemini_or_raise().embed(text)

    def embed_query(self, text: str) -> Dict:
        if self._embed_mode == "gemini":
            try:
                return self._gemini_or_raise().embed_query(text)
            except Exception:
                return self._ollama.embed_query(text)
        try:
            return self._ollama.embed_query(text)
        except Exception:
            return self._gemini_or_raise().embed_query(text)

    def chat(self, messages: Optional[List[dict]] = None, system: Optional[str] = None,
             tools: Optional[list] = None, tool_choice: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.3,
             prompt: Optional[str] = None) -> Dict:
        if self._gemini is not None:
            try:
                return self._gemini.chat(messages, system, tools, tool_choice,
                                         max_tokens, temperature, prompt)
            except Exception:
                pass
        return self._ollama.chat(messages, system, tools, tool_choice,
                                 max_tokens, temperature, prompt)
