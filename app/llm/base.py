"""LLM interface. All app code depends on this, not on any concrete provider."""
from typing import Dict, List, Optional


class LLMProvider:
    def embed(self, text: str) -> Dict:
        raise NotImplementedError

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed many document texts. Default: one by one; adapters may override
        with a true batch API (Gemini does)."""
        return [self.embed(t)["embedding"] for t in texts]

    def embed_query(self, text: str) -> Dict:
        raise NotImplementedError

    def chat(self, messages: Optional[List[dict]] = None, system: Optional[str] = None,
             tools: Optional[list] = None, tool_choice: Optional[str] = None,
             max_tokens: int = 1024, temperature: float = 0.3,
             prompt: Optional[str] = None) -> Dict:
        raise NotImplementedError
