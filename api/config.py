from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # Ollama configuration
    ollama_host: str = "http://localhost:11434"
    default_model: str = "mistral:7b"
    embedding_model: str = "nomic-embed-text:latest"
    embedding_dim: int = 768

    # Database settings
    database_url: Optional[str] = None
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Auto-ingest configuration
    auto_ingest_on_start: bool = True
    auto_ingest_path: Optional[str] = None
    auto_ingest_watch_mode: bool = False
    auto_ingest_watch_interval: int = 600

    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate limiting (removed for simplicity)

    # Performance configuration
    embedding_batch_size: int = 10
    max_concurrent_requests: int = 5
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Monitoring (removed for simplicity)

    # Feature flags
    enable_streaming: bool = False
    enable_conversation_memory: bool = False
    enable_hybrid_search: bool = False
    enable_incremental_ingestion: bool = True
    
    # Response caching
    cache_max_size: int = 1000
    cache_ttl_seconds: int = 3600  # 1 hour
    enable_response_cache: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
