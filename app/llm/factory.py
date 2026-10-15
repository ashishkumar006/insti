"""Select LLM backend by env. direct = Ollama + Gemini, no gateway."""
from app.config import cfg
from app.llm.base import LLMProvider
from app.llm.direct_adapter import DirectAdapter

_llm = None


def get_llm() -> LLMProvider:
    global _llm
    if _llm is not None:
        return _llm
    if cfg.llm_mode == "direct":
        _llm = DirectAdapter()
    else:
        # Gateway path retired to archive/retired-direct-only/ - kept lazy so
        # direct mode never imports it.
        try:
            from app.llm.gateway_adapter import GatewayAdapter  # type: ignore
        except ImportError:
            raise RuntimeError(
                "LLM_MODE=gateway but app/llm/gateway_adapter.py was archived "
                "(see archive/retired-direct-only/). Set LLM_MODE=direct."
            )
        _llm = GatewayAdapter()
    return _llm
