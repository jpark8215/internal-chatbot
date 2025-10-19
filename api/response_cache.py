"""
Response caching for improved performance and reduced LLM calls.
"""

import hashlib
import json
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from threading import Lock

from .config import get_settings
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CachedResponse:
    """Cached response data."""
    text: str
    sources: list
    model_used: str
    timestamp: float
    hit_count: int = 1
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if cache entry is expired."""
        return time.time() - self.timestamp > ttl_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ResponseCache:
    """In-memory response cache with TTL and LRU eviction."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, CachedResponse] = {}
        self.access_order: list = []  # For LRU
        self.lock = Lock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def _generate_cache_key(self, query: str, system_prompt: Optional[str] = None, 
                          model: Optional[str] = None) -> str:
        """Generate cache key from query parameters."""
        # Normalize query for better cache hits
        normalized_query = query.strip().lower()
        
        # Use simpler hash for better performance
        content = f"{normalized_query}:{system_prompt or ''}:{model or ''}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def get(self, query: str, system_prompt: Optional[str] = None, 
            model: Optional[str] = None) -> Optional[CachedResponse]:
        """Get cached response if available and not expired."""
        cache_key = self._generate_cache_key(query, system_prompt, model)
        
        with self.lock:
            if cache_key not in self.cache:
                self.misses += 1
                return None
            
            cached_response = self.cache[cache_key]
            
            # Check if expired
            if cached_response.is_expired(self.ttl_seconds):
                del self.cache[cache_key]
                if cache_key in self.access_order:
                    self.access_order.remove(cache_key)
                self.misses += 1
                return None
            
            # Update access order for LRU
            if cache_key in self.access_order:
                self.access_order.remove(cache_key)
            self.access_order.append(cache_key)
            
            # Update hit count
            cached_response.hit_count += 1
            self.hits += 1
            
            logger.debug(f"Cache hit for query: {query[:50]}...")
            return cached_response
    
    def put(self, query: str, response_text: str, sources: list, model_used: str,
            system_prompt: Optional[str] = None) -> None:
        """Cache a response."""
        cache_key = self._generate_cache_key(query, system_prompt, model_used)
        
        with self.lock:
            # Create cached response
            cached_response = CachedResponse(
                text=response_text,
                sources=sources,
                model_used=model_used,
                timestamp=time.time()
            )
            
            # Add to cache
            self.cache[cache_key] = cached_response
            
            # Update access order
            if cache_key in self.access_order:
                self.access_order.remove(cache_key)
            self.access_order.append(cache_key)
            
            # Evict if over max size
            while len(self.cache) > self.max_size:
                oldest_key = self.access_order.pop(0)
                if oldest_key in self.cache:
                    del self.cache[oldest_key]
                    self.evictions += 1
            
            logger.debug(f"Cached response for query: {query[:50]}...")
    
    def clear(self) -> None:
        """Clear all cached responses."""
        with self.lock:
            self.cache.clear()
            self.access_order.clear()
            logger.info("Response cache cleared")
    
    def invalidate_by_source(self, source_file: str) -> int:
        """Invalidate cached responses that used a specific source file."""
        invalidated_count = 0
        
        with self.lock:
            keys_to_remove = []
            
            for cache_key, cached_response in self.cache.items():
                # Check if any of the sources match the deleted file
                for source in cached_response.sources:
                    if source.get('source_file') and source_file in source.get('source_file', ''):
                        keys_to_remove.append(cache_key)
                        break
            
            # Remove invalidated entries
            for key in keys_to_remove:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)
                invalidated_count += 1
        
        if invalidated_count > 0:
            logger.info(f"Invalidated {invalidated_count} cached responses using source: {source_file}")
        
        return invalidated_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "cache_size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate, 2),
                "evictions": self.evictions,
                "ttl_seconds": self.ttl_seconds
            }
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count removed."""
        removed_count = 0
        current_time = time.time()
        
        with self.lock:
            expired_keys = []
            for key, response in self.cache.items():
                if current_time - response.timestamp > self.ttl_seconds:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)
                removed_count += 1
        
        if removed_count > 0:
            logger.debug(f"Cleaned up {removed_count} expired cache entries")
        
        return removed_count


# Global cache instance
_response_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    """Get or create the response cache instance."""
    global _response_cache
    if _response_cache is None:
        settings = get_settings()
        # Configure cache based on settings
        max_size = getattr(settings, 'cache_max_size', 1000)
        ttl_seconds = getattr(settings, 'cache_ttl_seconds', 3600)
        _response_cache = ResponseCache(max_size=max_size, ttl_seconds=ttl_seconds)
    return _response_cache