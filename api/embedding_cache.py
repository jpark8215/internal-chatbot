"""
High-performance embedding cache for repeated queries.
"""

import hashlib
import time
from typing import List, Optional, Dict
from threading import Lock
from collections import OrderedDict

from .config import get_settings
from .logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingCache:
    """LRU cache for embeddings with TTL."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.lock = Lock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, text: str, model: str) -> str:
        """Generate cache key from text and model."""
        content = f"{text}:{model}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, text: str, model: str) -> Optional[List[float]]:
        """Get cached embedding if available and not expired."""
        key = self._generate_key(text, model)
        
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            embedding, timestamp = self.cache[key]
            
            # Check if expired
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            
            return embedding
    
    def put(self, text: str, model: str, embedding: List[float]) -> None:
        """Cache an embedding."""
        key = self._generate_key(text, model)
        
        with self.lock:
            # Add/update cache entry
            self.cache[key] = (embedding, time.time())
            self.cache.move_to_end(key)
            
            # Evict oldest if over max size
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "cache_size": len(self.cache),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate, 2)
            }
    
    def clear(self) -> None:
        """Clear all cached embeddings."""
        with self.lock:
            self.cache.clear()
            logger.info("Embedding cache cleared")


# Global cache instance
_embedding_cache: Optional[EmbeddingCache] = None


def get_embedding_cache() -> EmbeddingCache:
    """Get or create the embedding cache instance."""
    global _embedding_cache
    if _embedding_cache is None:
        settings = get_settings()
        cache_size = getattr(settings, 'embedding_cache_size', 1000)
        _embedding_cache = EmbeddingCache(max_size=cache_size)
    return _embedding_cache