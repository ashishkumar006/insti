"""LLM interface. All code depends on this, never on gateway directly."""
from typing import Dict, List, Optional


class LLMProvider:
    def embed(self, text: str) -> Dict:
        raise NotImplementedError

    def embed_query(self, text: str) -> Dict:
        raise NotImplementedError

    def chat(self, messages: Optional[List[dict]] = None, system: Optional[str] = None,
             tools: Optional[list] = None, tool_choice: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.3,
             prompt: Optional[str] = None) -> Dict:
        raise NotImplementedError
