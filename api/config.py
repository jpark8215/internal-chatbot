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
    ollama_host: str = "http://host.docker.internal:11434"
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
    database_pool_size: int = 100  # Increased for better concurrency
    database_max_overflow: int = 200  # Increased overflow capacity
    database_query_timeout: int = 3  # Query timeout in seconds
    database_connection_timeout: int = 10  # Connection timeout in seconds

    # Auto-ingest configuration
    auto_ingest_on_start: bool = True
    auto_ingest_path: Optional[str] = None
    auto_ingest_watch_mode: bool = False
    auto_ingest_watch_interval: int = 600
    auto_ingest_max_retries: int = 5
    auto_ingest_retry_initial_delay: float = 2.0
    auto_ingest_retry_max_delay: float = 30.0
    auto_ingest_file_ready_timeout: float = 60.0
    auto_ingest_file_ready_poll_interval: float = 1.0
    auto_ingest_file_ready_stability_checks: int = 2
    auto_ingest_run_periodic_checker: bool = True
    
    # Scheduled cleanup configuration
    enable_scheduled_cleanup: bool = True
    cleanup_interval: int = 600 

    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate limiting (removed for simplicity)

    # Performance configuration
    embedding_batch_size: int = 50
    max_concurrent_requests: int = 20
    chunk_size: int = 400
    chunk_overlap: int = 0
    
    # Response time optimizations
    enable_fast_mode: bool = True
    skip_quality_indicators: bool = True  # Skip for faster responses
    enable_query_parallelization: bool = True
    database_query_timeout: int = 3  # Reduced timeout for faster failure
    llm_generation_timeout: int = 15  # Reduced timeout for faster responses
    
    # Caching optimizations
    enable_embedding_cache: bool = True
    embedding_cache_size: int = 2000  # Increased cache size
    enable_query_result_cache: bool = True
    query_result_cache_ttl: int = 600  

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
