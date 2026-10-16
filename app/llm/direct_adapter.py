"""Direct adapter: Gemini for embeddings and chat; Ollama chat only as an
offline-dev fallback.

Embeddings are Gemini-only by design: mixing embedding models inside one index
silently corrupts retrieval, so a missing key fails loudly instead of falling
back to a different model.
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

    def _gemini_or_raise(self):
        if self._gemini is None:
            raise RuntimeError(
                "GEMINI_API_KEY is not set - Gemini is the only embedding provider")
        return self._gemini

    def embed(self, text: str, title: str = "") -> Dict:
        return self._gemini_or_raise().embed(text, title)

    def embed_image(self, data: bytes, mime: str = "image/png", title: str = "") -> Dict:
        return self._gemini_or_raise().embed_image(data, mime, title)

    def embed_images_batch(self, items: list, title: str = "") -> List[List[float]]:
        return self._gemini_or_raise().embed_images_batch(items, title)

    def embed_batch(self, texts: List[str], title: str = "") -> List[List[float]]:
        return self._gemini_or_raise().embed_batch(texts, title)

    def embed_query(self, text: str) -> Dict:
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
