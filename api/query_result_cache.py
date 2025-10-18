"""
Query result caching for database queries to reduce retrieval time.
"""

import hashlib
import json
import time
from typing import List, Tuple, Optional, Dict, Any
from threading import Lock
from collections import OrderedDict

from .config import get_settings
from .logging_config import get_logger

logger = get_logger(__name__)


class QueryResultCache:
    """Cache for database query results with TTL."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.lock = Lock()
        
        # Statistics
        self.hits = 0
        self.misses = 0
    
    def _generate_key(self, query_type: str, query_params: Dict[str, Any]) -> str:
        """Generate cache key from query type and parameters."""
        content = {
            "type": query_type,
            "params": query_params
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]
    
    def get(self, query_type: str, query_params: Dict[str, Any]) -> Optional[List[Tuple]]:
        """Get cached query result if available and not expired."""
        key = self._generate_key(query_type, query_params)
        
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return None
            
            result, timestamp = self.cache[key]
            
            # Check if expired
            if time.time() - timestamp > self.ttl_seconds:
                del self.cache[key]
                self.misses += 1
                return None
            
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            self.hits += 1
            
            return result
    
    def put(self, query_type: str, query_params: Dict[str, Any], result: List[Tuple]) -> None:
        """Cache a query result."""
        key = self._generate_key(query_type, query_params)
        
        with self.lock:
            # Add/update cache entry
            self.cache[key] = (result, time.time())
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
        """Clear all cached query results."""
        with self.lock:
            self.cache.clear()
            logger.info("Query result cache cleared")
    
    def invalidate_by_source(self, source_file: str) -> int:
        """Invalidate cached query results that contain documents from a specific source file."""
        invalidated_count = 0
        
        with self.lock:
            keys_to_remove = []
            
            for cache_key, (result, timestamp) in self.cache.items():
                # Check if any documents in the result are from the deleted source
                for doc_id, content, score, doc_source_file in result:
                    if doc_source_file and source_file in doc_source_file:
                        keys_to_remove.append(cache_key)
                        break
            
            # Remove invalidated entries
            for key in keys_to_remove:
                del self.cache[key]
                invalidated_count += 1
        
        if invalidated_count > 0:
            logger.info(f"Invalidated {invalidated_count} cached query results using source: {source_file}")
        
        return invalidated_count


# Global cache instance
_query_result_cache: Optional[QueryResultCache] = None


def get_query_result_cache() -> QueryResultCache:
    """Get or create the query result cache instance."""
    global _query_result_cache
    if _query_result_cache is None:
        settings = get_settings()
        ttl = getattr(settings, 'query_result_cache_ttl', 300)
        _query_result_cache = QueryResultCache(ttl_seconds=ttl)
    return _query_result_cache