"""
Query result caching for database queries to reduce retrieval time.
"""

import hashlib
import json
import time
from typing import List, Tuple, Optional, Dict, Any

from threading import Lock
from collections import OrderedDict, defaultdict

from .config import get_settings
from .logging_config import get_logger

logger = get_logger(__name__)


class QueryResultCache:
    """Cache for database query results with TTL."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.query_index: Dict[str, List[str]] = defaultdict(list)  # map query_text -> [cache_keys]
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
            
            # Index by query text if available
            if "query" in query_params:
                query_text = str(query_params["query"]).lower().strip()
                if key not in self.query_index[query_text]:
                    self.query_index[query_text].append(key)
            
            # Evict oldest if over max size
            while len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
                # Note: We don't clean up query_index here for performance, 
                # but invalidate_by_text handles missing keys gracefully.
                # Periodic clear() or restart cleans it up.
    
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
            self.query_index.clear()
            logger.info("Query result cache cleared")
    
    def invalidate_by_source(self, source_file: str) -> int:
        """Invalidate cached query results that contain documents from a specific source file."""
        invalidated_count = 0
        target = (source_file or "").strip()
        if not target:
            return 0
        
        with self.lock:
            keys_to_remove = []
            
            for cache_key, (result, timestamp) in self.cache.items():
                # Check if any documents in the result are from the deleted source.
                # Cached results may be:
                # - List[DocumentResult]
                # - List[Tuple[id, content, score, source_file]]
                # - List[Dict] (defensive)
                try:
                    for item in (result or []):
                        doc_source_file = None
                        if isinstance(item, tuple) and len(item) >= 4:
                            doc_source_file = item[3]
                        elif isinstance(item, dict):
                            doc_source_file = item.get("source_file")
                        else:
                            # DocumentResult-like object
                            doc_source_file = getattr(item, "source_file", None)

                        if doc_source_file and target in str(doc_source_file):
                            keys_to_remove.append(cache_key)
                            break
                except Exception as e:
                    logger.warning(f"Failed to inspect cached result for source invalidation (key={cache_key}): {e}")

            # Remove invalidated entries
            for key in keys_to_remove:
                del self.cache[key]
                invalidated_count += 1

            # Best-effort cleanup: remove invalidated keys from query_index lists.
            # This keeps invalidate_by_text effective even after source invalidations.
            if keys_to_remove:
                for query_text, key_list in list(self.query_index.items()):
                    new_list = [k for k in key_list if k not in keys_to_remove]
                    if new_list:
                        self.query_index[query_text] = new_list
                    else:
                        del self.query_index[query_text]
        
        if invalidated_count > 0:
            logger.info(f"Invalidated {invalidated_count} cached query results using source: {source_file}")
        
        return invalidated_count

    def invalidate_by_text(self, query_text: str) -> int:
        """Invalidate cached results for a specific query text."""
        invalidated_count = 0
        target_query = query_text.lower().strip()
        
        with self.lock:
            keys_to_remove = self.query_index.get(target_query, [])
            
            # Also try to match partial queries or similar ones if needed,
            # but for now exact normalized match is safer.
            
            valid_keys_to_remove = []
            for key in keys_to_remove:
                if key in self.cache:
                    del self.cache[key]
                    valid_keys_to_remove.append(key)
                    invalidated_count += 1
            
            # Remove from index
            if target_query in self.query_index:
                del self.query_index[target_query]
                
        if invalidated_count > 0:
            logger.info(f"Invalidated {invalidated_count} cache entries for query: '{target_query}'")
            
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