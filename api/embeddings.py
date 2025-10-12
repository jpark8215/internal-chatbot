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

        # Process texts in batches for better performance
        batch_size = settings.embedding_batch_size
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Process batch concurrently
            batch_tasks = []
            for text in batch:
                payload = {"model": model_name, "prompt": text}
                batch_tasks.append(
                    session.post(
                        f"{settings.ollama_host}/api/embeddings",
                        json=payload
                    )
                )

            # Wait for all requests in batch to complete
            batch_responses = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for resp in batch_responses:
                if isinstance(resp, Exception):
                    raise RuntimeError(f"Failed to call Ollama embeddings: {resp}")

                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"Ollama embeddings returned {resp.status}: {error_text}")

                data = await resp.json()
                vector = data.get("embedding")
                if not vector:
                    raise ValueError(f"No embedding in response: {data}")
                embeddings.append(vector)

        return embeddings


async def embed_texts_batch(texts: List[str], model: Optional[str] = None,
                          max_concurrent: Optional[int] = None) -> List[List[float]]:
    """Get embeddings with controlled concurrency to avoid overwhelming Ollama."""
    settings = get_settings()
    model_name = model or settings.embedding_model
    max_concurrent = max_concurrent or settings.max_concurrent_requests

    await ensure_ollama_model(model_name)

    async def embed_single_text(session: aiohttp.ClientSession, text: str) -> List[float]:
        """Embed a single text."""
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
                return vector
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Failed to call Ollama embeddings: {e}")

    async with aiohttp.ClientSession() as session:
        # Use semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)

        async def embed_with_semaphore(text: str) -> List[float]:
            async with semaphore:
                return await embed_single_text(session, text)

        # Process all texts concurrently with rate limiting
        tasks = [embed_with_semaphore(text) for text in texts]
        embeddings = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        result = []
        for i, embedding in enumerate(embeddings):
            if isinstance(embedding, Exception):
                raise RuntimeError(f"Failed to embed text {i}: {embedding}")
            result.append(embedding)

        return result


def embed_texts_sync(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    """Synchronous wrapper for embedding texts."""
    return asyncio.run(embed_texts(texts, model=model))


def embed_texts_batch_sync(texts: List[str], model: Optional[str] = None,
                          max_concurrent: Optional[int] = None) -> List[List[float]]:
    """Synchronous wrapper for batch embedding with concurrency control."""
    return asyncio.run(embed_texts_batch(texts, model=model, max_concurrent=max_concurrent))
