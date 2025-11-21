from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """Request model for text generation."""
    prompt: str = Field(..., description="The prompt to send to the model")
    max_tokens: int = Field(256, ge=1, le=4096, description="Maximum number of tokens to generate")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt for chat context")


class GenerateResponse(BaseModel):
    """Response model for text generation."""
    ok: bool = Field(..., description="Whether the generation was successful")
    text: Optional[str] = Field(None, description="Generated text if successful")
    reason: Optional[str] = Field(None, description="Error reason if not successful")
    model: Optional[str] = Field(None, description="Model used for generation")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="Source documents used for the response")
    search_strategy: Optional[str] = Field(None, description="Search strategy used for document retrieval")
    quality_indicators: Optional[Dict[str, Any]] = Field(None, description="Quality indicators based on historical feedback")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Overall API status")
    db: str = Field(..., description="Database connection status")
    local_llm: str = Field(..., description="Local LLM availability status")


# Lightweight dataclass for normalized document results returned by the DAO
from dataclasses import dataclass


@dataclass
class DocumentResult:
    id: int
    content: str
    score: float
    source_file: Optional[str] = None
    chunk_index: Optional[int] = None
    start_position: Optional[int] = None
    end_position: Optional[int] = None
    page_number: Optional[int] = None
