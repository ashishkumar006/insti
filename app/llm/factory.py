"""Select LLM backend by env. direct = Ollama + Gemini, no gateway."""
from app.config import cfg
from app.llm.base import LLMProvider
from app.llm.gateway_adapter import GatewayAdapter
from app.llm.direct_adapter import DirectAdapter

_llm = None


def get_llm() -> LLMProvider:
    global _llm
    if _llm is not None:
        return _llm
    if cfg.llm_mode == "direct":
        _llm = DirectAdapter()
    else:
        _llm = GatewayAdapter()
    return _llm
