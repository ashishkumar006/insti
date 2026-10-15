"""LLM backend. Direct adapter only: Gemini + optional local Ollama chat."""
from app.llm.base import LLMProvider
from app.llm.direct_adapter import DirectAdapter

_llm = None


def get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = DirectAdapter()
    return _llm
