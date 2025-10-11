from typing import Optional
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    ollama_host: str = "http://localhost:11434"
    default_model: str = "mistral:7b"
    # Embeddings config
    embedding_model: str = "nomic-embed-text:latest"
    embedding_dim: int = 768
    auto_ingest_on_start: bool = True
    auto_ingest_path: Optional[str] = None    # Auto-ingest

    # Database settings
    database_url: Optional[str] = None  # e.g., postgres://user:pass@host:5432/db
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    # Load from .env if present
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()