"""Gateway adapter (legacy path). Wraps previous gateway wire format."""
from typing import Dict, List, Optional
import httpx

from app.config import cfg
from app.llm.base import LLMProvider


class GatewayAdapter(LLMProvider):
    def __init__(self, base_url: str = "", embed_provider: str = ""):
        self.base_url = (base_url or cfg.gateway_url).rstrip("/")
        self.embed_provider = embed_provider or cfg.embed_provider

    def _call(self, path: str, payload: dict) -> dict:
        with httpx.Client(timeout=120.0) as c:
            r = c.post(self.base_url + path, json=payload)
            r.raise_for_status()
            return r.json()

    def embed(self, text: str) -> Dict:
        body = {"text": text, "task_type": "retrieval_document"}
        if self.embed_provider:
            body["provider"] = self.embed_provider
        return self._call("/v1/embed", body)

    def embed_query(self, text: str) -> Dict:
        body = {"text": text, "task_type": "retrieval_query"}
        if self.embed_provider:
            body["provider"] = self.embed_provider
        return self._call("/v1/embed", body)

    def chat(self, messages: Optional[List[dict]] = None, system: Optional[str] = None,
             tools: Optional[list] = None, tool_choice: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.3,
             prompt: Optional[str] = None) -> Dict:
        body: dict = {"max_tokens": max_tokens, "temperature": temperature, "stream": False}
        if prompt is not None:
            body["prompt"] = prompt
        if system is not None:
            body["system"] = system
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        if messages is not None:
            body["messages"] = messages
        if cfg.llm_provider:
            body["provider"] = cfg.llm_provider
        return self._call("/v1/chat", body)
