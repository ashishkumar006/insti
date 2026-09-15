import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Database (PostgreSQL is primary) ---
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://campus:campus@localhost:5432/campusguide",
    )
    # --- LLM: gateway now, direct pay-go later ---
    llm_mode: str = os.getenv("LLM_MODE", "gateway")  # gateway | direct
    gateway_url: str = os.getenv("GATEWAY_URL", "http://localhost:8109")
    llm_provider: str = os.getenv("LLM_PROVIDER", "")
    embed_provider: str = os.getenv("EMBED_PROVIDER", "ollama")
    paygo_api_key: str = os.getenv("PAYGO_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    # Cloud: nothing runs local — set EMBED_MODE=gemini so no localhost call is attempted.
    embed_mode: str = os.getenv("EMBED_MODE", "ollama")  # ollama | gemini
    ocr_mode: str = os.getenv("OCR_MODE", "auto")  # auto | gemini | ollama | off
    ollama_url: str = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    ollama_chat_model: str = os.getenv("OLLAMA_CHAT_MODEL", "phi4-mini")
    paygo_chat_model: str = os.getenv("PAYGO_CHAT_MODEL", "gemini-2.0-flash")
    paygo_embed_model: str = os.getenv("PAYGO_EMBED_MODEL", "gemini-embedding-001")
    # --- Retrieval / chunking ---
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "750"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "75"))
    top_k: int = int(os.getenv("TOP_K", "10"))
    fusion_k: int = int(os.getenv("FUSION_K", "60"))
    dense_weight: float = float(os.getenv("DENSE_WEIGHT", "0.5"))
    sparse_weight: float = float(os.getenv("SPARSE_WEIGHT", "0.5"))
    embed_dim: int = int(os.getenv("EMBED_DIM", "768"))
    embed_batch_size: int = int(os.getenv("EMBED_BATCH_SIZE", "32"))
    # --- Local index dirs (legacy file stores) ---
    index_dir: str = os.getenv("INDEX_DIR", "indexes")
    data_dir: str = os.getenv("DATA_DIR", "data")
    # --- Auth ---
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-only-change-me")
    jwt_hours: int = int(os.getenv("JWT_HOURS", "12"))
    admin_email: str = os.getenv("ADMIN_EMAIL", "")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "")
    # --- Uploads ---
    storage_dir: str = os.getenv("STORAGE_DIR", "var/uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "20"))

    model_config = {"env_file": ".env", "extra": "ignore"}


cfg = Settings()
