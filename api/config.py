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
    database_pool_size: int = 50
    database_max_overflow: int = 100

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
    embedding_batch_size: int = 50
    max_concurrent_requests: int = 20
    chunk_size: int = 1000
    chunk_overlap: int = 200
    
    # Response time optimizations
    enable_fast_mode: bool = True
    skip_quality_indicators: bool = False
    enable_query_parallelization: bool = True
    database_query_timeout: int = 5  # seconds
    llm_generation_timeout: int = 30  # seconds
    
    # Caching optimizations
    enable_embedding_cache: bool = True
    embedding_cache_size: int = 1000
    enable_query_result_cache: bool = True
    query_result_cache_ttl: int = 300  # 5 minutes

    # Monitoring (removed for simplicity)

    # Feature flags
    enable_streaming: bool = False
    enable_conversation_memory: bool = False
    enable_hybrid_search: bool = False
    enable_incremental_ingestion: bool = True
    
    # Response caching
    cache_max_size: int = 10000
    cache_ttl_seconds: int = 7200  
    enable_response_cache: bool = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
