import asyncio
from typing import List, Optional

import aiohttp

from .config import get_settings


async def ensure_ollama_model(model: str) -> None:
    """Ensure the Ollama embedding model is available by calling the pull API.
    Safe to call; will no-op if already pulled.
    """
    settings = get_settings()
    async with aiohttp.ClientSession() as session:
        try:
            # POST /api/pull { "name": model }
            async with session.post(
                f"{settings.ollama_host}/api/pull", json={"name": model}
            ) as resp:
                # The pull API streams progress; we don't need to consume all chunks to be effective.
                # Consider non-200 as warning but non-fatal.
                if resp.status not in (200, 204):
                    await resp.read()
        except aiohttp.ClientError:
            # If Ollama isn't reachable, just return; callers should handle failure gracefully.
            return


async def embed_texts(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    """Get embeddings from Ollama for a batch of texts.
    Returns list of vectors.
    """
    settings = get_settings()
    model_name = model or settings.embedding_model

    await ensure_ollama_model(model_name)

    async with aiohttp.ClientSession() as session:
        embeddings: List[List[float]] = []
        for text in texts:
            payload = {"model": model_name, "prompt": text}
            try:
                async with session.post(
                    f"{settings.ollama_host}/api/embeddings", json=payload
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        raise RuntimeError(f"Ollama embeddings returned {resp.status}: {error_text}")
                    data = await resp.json()
                    vector = data.get("embedding")
                    if not vector:
                        raise ValueError(f"No embedding in response: {data}")
                    embeddings.append(vector)
            except aiohttp.ClientError as e:
                raise RuntimeError(f"Failed to call Ollama embeddings: {e}")
        return embeddings


def embed_texts_sync(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    return asyncio.run(embed_texts(texts, model=model))
