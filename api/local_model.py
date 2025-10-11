import asyncio
import json
from typing import Optional, Dict, Any
import aiohttp
from .config import get_settings
from .models import GenerateRequest


class OllamaError(Exception):
    """Base exception for Ollama-related errors."""
    pass


class ModelNotFoundError(OllamaError):
    """Raised when the requested model is not available."""
    pass


class GenerationError(OllamaError):
    """Raised when text generation fails."""
    pass


class LocalLLM:
    """Asynchronous client for local Ollama instance."""
    
    def __init__(self):
        self.settings = get_settings()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
    
    async def check_model(self, model_name: str) -> bool:
        """Check if a model is available locally."""
        session = await self._ensure_session()
        try:
            async with session.get(f"{self.settings.ollama_host}/api/tags") as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                return any(model["name"] == model_name for model in data["models"])
        except aiohttp.ClientError:
            return False
    
    async def generate(self, request: GenerateRequest, model: Optional[str] = None) -> Dict[str, Any]:
        """Generate text using the local Ollama instance.
        
        Args:
            request: The generation request parameters
            model: Optional model name override
        
        Returns:
            Dict containing generation result with 'ok' and either 'text' or 'reason'
        
        Raises:
            ModelNotFoundError: If the requested model is not available
            GenerationError: If the generation request fails
        """
        model_name = model or self.settings.default_model
        
        # Verify model availability
        if not await self.check_model(model_name):
            raise ModelNotFoundError(f"Model {model_name} not found")
        
        session = await self._ensure_session()
        
        # Prepare request payload
        payload = {
            "model": model_name,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            }
        }
        
        if request.system_prompt:
            payload["system"] = request.system_prompt
        
        try:
            async with session.post(
                f"{self.settings.ollama_host}/api/generate",
                json=payload
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise GenerationError(f"Generation failed: {error_text}")
                
                data = await resp.json()
                return {
                    "ok": True,
                    "text": data.get("response", ""),
                    "model": model_name
                }
                
        except aiohttp.ClientError as e:
            raise GenerationError(f"Failed to communicate with Ollama: {str(e)}")
        
    async def get_models(self) -> list[str]:
        """Get list of available models."""
        session = await self._ensure_session()
        try:
            async with session.get(f"{self.settings.ollama_host}/api/tags") as resp:
                if resp.status != 200:
                    raise OllamaError("Failed to fetch models")
                data = await resp.json()
                return [model["name"] for model in data["models"]]
        except aiohttp.ClientError as e:
            raise OllamaError(f"Failed to communicate with Ollama: {str(e)}")


# Single instance for the application
_default_llm: Optional[LocalLLM] = None


def get_local_llm() -> LocalLLM:
    """Get or create the default LocalLLM instance."""
    global _default_llm
    if _default_llm is None:
        _default_llm = LocalLLM()
    return _default_llm
