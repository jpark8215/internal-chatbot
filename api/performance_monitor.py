"""
Performance monitoring and optimization recommendations.
"""

import time
import psutil
from typing import Dict, Any, List
from dataclasses import dataclass

from .config import get_settings
from .dao import get_dao
from .response_cache import get_response_cache
from .embedding_cache import get_embedding_cache
from .query_result_cache import get_query_result_cache
from .metrics import get_metrics_collector
from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """System performance metrics."""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    response_cache_stats: Dict[str, Any]
    embedding_cache_stats: Dict[str, Any]
    query_cache_stats: Dict[str, Any]
    database_pool_stats: Dict[str, Any]
    avg_response_time_ms: float
    p95_response_time_ms: float
    cache_hit_rate: float
    recommendations: List[str]


class PerformanceMonitor:
    """Monitor system performance and provide optimization recommendations."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def get_system_metrics(self) -> PerformanceMetrics:
        """Get comprehensive system performance metrics."""
        # System resources
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Cache statistics
        response_cache = get_response_cache()
        embedding_cache = get_embedding_cache()
        query_cache = get_query_result_cache()
        
        response_cache_stats = response_cache.get_stats()
        embedding_cache_stats = embedding_cache.get_stats()
        query_cache_stats = query_cache.get_stats()
        
        # Database pool stats
        dao = get_dao()
        pool = dao._connection_pool
        database_pool_stats = {
            "total_connections": pool.maxconn if pool else 0,
            "available_connections": len(pool._pool) if pool and hasattr(pool, '_pool') else 0,
            "pool_size": self.settings.database_pool_size,
            "max_overflow": self.settings.database_max_overflow
        }
        
        # Performance metrics
        metrics_collector = get_metrics_collector()
        system_metrics = metrics_collector.get_system_metrics(time_window_minutes=60)
        
        avg_response_time = system_metrics.avg_total_time_ms
        p95_response_time = system_metrics.p95_total_time_ms
        cache_hit_rate = system_metrics.cache_hit_rate
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            cpu_percent, memory_percent, response_cache_stats, 
            embedding_cache_stats, query_cache_stats, avg_response_time
        )
        
        return PerformanceMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_available_mb=memory_available_mb,
            response_cache_stats=response_cache_stats,
            embedding_cache_stats=embedding_cache_stats,
            query_cache_stats=query_cache_stats,
            database_pool_stats=database_pool_stats,
            avg_response_time_ms=avg_response_time,
            p95_response_time_ms=p95_response_time,
            cache_hit_rate=cache_hit_rate,
            recommendations=recommendations
        )
    
    def _generate_recommendations(self, cpu_percent: float, memory_percent: float,
                                response_cache_stats: Dict, embedding_cache_stats: Dict,
                                query_cache_stats: Dict, avg_response_time: float) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        
        # CPU recommendations
        if cpu_percent > 80:
            recommendations.append("High CPU usage detected. Consider scaling horizontally or optimizing query complexity.")
        
        # Memory recommendations
        if memory_percent > 85:
            recommendations.append("High memory usage detected. Consider reducing cache sizes or adding more RAM.")
        
        # Cache recommendations
        response_hit_rate = response_cache_stats.get("hit_rate", 0)
        if response_hit_rate < 20:
            recommendations.append("Low response cache hit rate. Consider increasing cache TTL or size.")
        
        embedding_hit_rate = embedding_cache_stats.get("hit_rate", 0)
        if embedding_hit_rate < 30:
            recommendations.append("Low embedding cache hit rate. Consider increasing embedding cache size.")
        
        query_hit_rate = query_cache_stats.get("hit_rate", 0)
        if query_hit_rate < 25:
            recommendations.append("Low query result cache hit rate. Consider increasing query cache TTL.")
        
        # Response time recommendations
        if avg_response_time > 5000:  # 5 seconds
            recommendations.append("High average response time. Enable fast mode and skip quality indicators.")
        elif avg_response_time > 3000:  # 3 seconds
            recommendations.append("Moderate response time. Consider enabling more aggressive caching.")
        
        # Database recommendations
        if not recommendations:
            recommendations.append("System performance is optimal. No immediate optimizations needed.")
        
        return recommendations
    
    def optimize_for_speed(self) -> Dict[str, Any]:
        """Apply automatic optimizations for speed."""
        optimizations_applied = []
        
        # Enable fast mode
        if not getattr(self.settings, 'enable_fast_mode', False):
            self.settings.enable_fast_mode = True
            optimizations_applied.append("Enabled fast mode")
        
        # Skip quality indicators
        if not getattr(self.settings, 'skip_quality_indicators', False):
            self.settings.skip_quality_indicators = True
            optimizations_applied.append("Enabled skipping quality indicators")
        
        # Increase cache sizes if memory allows
        memory = psutil.virtual_memory()
        if memory.percent < 70:  # If memory usage is below 70%
            response_cache = get_response_cache()
            if response_cache.max_size < 5000:
                response_cache.max_size = 5000
                optimizations_applied.append("Increased response cache size to 5000")
            
            embedding_cache = get_embedding_cache()
            if embedding_cache.max_size < 3000:
                embedding_cache.max_size = 3000
                optimizations_applied.append("Increased embedding cache size to 3000")
        
        return {
            "optimizations_applied": optimizations_applied,
            "timestamp": time.time()
        }


# Global instance
_performance_monitor: PerformanceMonitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor