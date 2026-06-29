from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM API
    # default="" only silences static type-checkers (Pylance) about a "missing argument";
    # the real value still loads from .env at runtime. Validated as non-empty below.
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/resume_analyzer.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma_db"
    chroma_collection_name: str = "resume_embeddings"

    # Embedding Model
    embedding_model: str = "all-MiniLM-L6-v2"

    # App / Server
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # CORS
    allowed_origins: str = "http://localhost:8501"

    # File handling
    upload_dir: str = "./data/sample_resumes"
    max_upload_size_mb: int = 10
    allowed_file_types: str = "pdf"

    # Concurrency / background tasks
    max_concurrent_llm_calls: int = 5
    use_celery: bool = False
    redis_url: str = "redis://localhost:6379/0"

    # Scoring weights
    weight_keyword_score: float = 0.4
    weight_semantic_score: float = 0.4
    weight_experience_score: float = 0.2

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def allowed_file_types_list(self) -> list[str]:
        return [ext.strip().lower() for ext in self.allowed_file_types.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — import this everywhere instead of instantiating Settings() directly."""
    return Settings()


settings = get_settings()