import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gateway_url: str = os.getenv("GATEWAY_URL", "http://localhost:8109")
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    top_k: int = int(os.getenv("TOP_K", "10"))
    fusion_k: int = int(os.getenv("FUSION_K", "60"))
    dense_weight: float = float(os.getenv("DENSE_WEIGHT", "0.5"))
    sparse_weight: float = float(os.getenv("SPARSE_WEIGHT", "0.5"))
    embed_batch_size: int = int(os.getenv("EMBED_BATCH_SIZE", "32"))
    index_dir: str = os.getenv("INDEX_DIR", "indexes")
    data_dir: str = os.getenv("DATA_DIR", "data")
    llm_provider: str = os.getenv("LLM_PROVIDER", "")
    embed_provider: str = os.getenv("EMBED_PROVIDER", "ollama")

    model_config = {"env_file": ".env", "extra": "ignore"}


cfg = Settings()
