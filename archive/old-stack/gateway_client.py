import httpx
from typing import Optional


class GatewayClient:
    def __init__(self, base_url: str, timeout: float = 120.0, default_provider: Optional[str] = None, embed_provider: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.default_provider = default_provider
        self.embed_provider = embed_provider

    def _provider(self, provider: Optional[str]) -> Optional[str]:
        if provider:
            return provider
        return self.default_provider or None

    def _call(self, method: str, path: str, payload: dict) -> dict:
        with httpx.Client(timeout=self.timeout) as c:
            r = getattr(c, method.lower())(f"{self.base_url}{path}", json=payload)
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                body = None
                try:
                    body = r.json()
                except Exception:
                    try:
                        body = r.text
                    except Exception:
                        body = None
                raise RuntimeError(body if body is not None else str(e)) from e
            return r.json()

    def embed(self, text: str, provider: Optional[str] = None) -> dict:
        body = {"text": text, "task_type": "retrieval_document"}
        p = self.embed_provider or provider or self.default_provider
        if p:
            body["provider"] = p
        return self._call("POST", "/v1/embed", body)

    def embed_query(self, text: str, provider: Optional[str] = None) -> dict:
        body = {"text": text, "task_type": "retrieval_query"}
        p = self.embed_provider or provider or self.default_provider
        if p:
            body["provider"] = p
        return self._call("POST", "/v1/embed", body)

    def chat(self, prompt: Optional[str] = None, system: Optional[str] = None, tools: Optional[list] = None,
             tool_choice: Optional[str] = None, max_tokens: int = 1024,
             temperature: float = 0.3, provider: Optional[str] = None,
             messages: Optional[list] = None) -> dict:
        body: dict = {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
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
        p = self._provider(provider)
        if p:
            body["provider"] = p
        return self._call("POST", "/v1/chat", body)
