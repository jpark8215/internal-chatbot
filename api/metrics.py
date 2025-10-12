"""
Performance metrics and monitoring for RAG system.
"""

import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque
from threading import Lock
from datetime import datetime, timedelta

from .logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class QueryMetrics:
    """Metrics for a single query."""
    query_id: str
    query_text: str
    timestamp: float
    retrieval_time_ms: float
    generation_time_ms: float
    total_time_ms: float
    documents_retrieved: int
    strategy_used: str
    model_used: str
    success: bool
    error_message: Optional[str] = None
    cache_hit: bool = False


@dataclass
class SystemMetrics:
    """Aggregated system metrics."""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    cache_hits: int = 0
    avg_retrieval_time_ms: float = 0.0
    avg_generation_time_ms: float = 0.0
    avg_total_time_ms: float = 0.0
    p95_total_time_ms: float = 0.0
    p99_total_time_ms: float = 0.0
    queries_per_minute: float = 0.0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0
    strategy_distribution: Dict[str, int] = field(default_factory=dict)
    model_distribution: Dict[str, int] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates RAG system metrics."""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.query_history: deque = deque(maxlen=max_history)
        self.lock = Lock()
        
        # Real-time counters
        self.total_queries = 0
        self.successful_queries = 0
        self.failed_queries = 0
        self.cache_hits = 0
        
        # Time-based metrics
        self.retrieval_times: deque = deque(maxlen=1000)
        self.generation_times: deque = deque(maxlen=1000)
        self.total_times: deque = deque(maxlen=1000)
        
        # Strategy and model tracking
        self.strategy_counts = defaultdict(int)
        self.model_counts = defaultdict(int)
        
        # Error tracking
        self.error_counts = defaultdict(int)
        self.recent_errors: deque = deque(maxlen=100)
    
    def record_query(self, metrics: QueryMetrics) -> None:
        """Record metrics for a single query."""
        with self.lock:
            # Add to history
            self.query_history.append(metrics)
            
            # Update counters
            self.total_queries += 1
            if metrics.success:
                self.successful_queries += 1
            else:
                self.failed_queries += 1
                if metrics.error_message:
                    self.error_counts[metrics.error_message] += 1
                    self.recent_errors.append({
                        'timestamp': metrics.timestamp,
                        'error': metrics.error_message,
                        'query': metrics.query_text[:100]
                    })
            
            if metrics.cache_hit:
                self.cache_hits += 1
            
            # Update time metrics
            self.retrieval_times.append(metrics.retrieval_time_ms)
            self.generation_times.append(metrics.generation_time_ms)
            self.total_times.append(metrics.total_time_ms)
            
            # Update strategy and model counts
            self.strategy_counts[metrics.strategy_used] += 1
            self.model_counts[metrics.model_used] += 1
    
    def get_system_metrics(self, time_window_minutes: int = 60) -> SystemMetrics:
        """Get aggregated system metrics for the specified time window."""
        with self.lock:
            current_time = time.time()
            cutoff_time = current_time - (time_window_minutes * 60)
            
            # Filter recent queries
            recent_queries = [
                q for q in self.query_history 
                if q.timestamp >= cutoff_time
            ]
            
            if not recent_queries:
                return SystemMetrics()
            
            # Calculate aggregated metrics
            total_queries = len(recent_queries)
            successful_queries = sum(1 for q in recent_queries if q.success)
            failed_queries = total_queries - successful_queries
            cache_hits = sum(1 for q in recent_queries if q.cache_hit)
            
            # Time metrics
            retrieval_times = [q.retrieval_time_ms for q in recent_queries]
            generation_times = [q.generation_time_ms for q in recent_queries]
            total_times = [q.total_time_ms for q in recent_queries]
            
            avg_retrieval_time = sum(retrieval_times) / len(retrieval_times) if retrieval_times else 0
            avg_generation_time = sum(generation_times) / len(generation_times) if generation_times else 0
            avg_total_time = sum(total_times) / len(total_times) if total_times else 0
            
            # Percentiles
            sorted_total_times = sorted(total_times)
            p95_index = int(0.95 * len(sorted_total_times))
            p99_index = int(0.99 * len(sorted_total_times))
            p95_total_time = sorted_total_times[p95_index] if sorted_total_times else 0
            p99_total_time = sorted_total_times[p99_index] if sorted_total_times else 0
            
            # Rates
            queries_per_minute = total_queries / time_window_minutes if time_window_minutes > 0 else 0
            error_rate = (failed_queries / total_queries * 100) if total_queries > 0 else 0
            cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0
            
            # Strategy and model distribution
            strategy_dist = defaultdict(int)
            model_dist = defaultdict(int)
            
            for query in recent_queries:
                strategy_dist[query.strategy_used] += 1
                model_dist[query.model_used] += 1
            
            return SystemMetrics(
                total_queries=total_queries,
                successful_queries=successful_queries,
                failed_queries=failed_queries,
                cache_hits=cache_hits,
                avg_retrieval_time_ms=round(avg_retrieval_time, 2),
                avg_generation_time_ms=round(avg_generation_time, 2),
                avg_total_time_ms=round(avg_total_time, 2),
                p95_total_time_ms=round(p95_total_time, 2),
                p99_total_time_ms=round(p99_total_time, 2),
                queries_per_minute=round(queries_per_minute, 2),
                error_rate=round(error_rate, 2),
                cache_hit_rate=round(cache_hit_rate, 2),
                strategy_distribution=dict(strategy_dist),
                model_distribution=dict(model_dist)
            )
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors."""
        with self.lock:
            return list(self.recent_errors)[-limit:]
    
    def get_slow_queries(self, threshold_ms: float = 5000, limit: int = 10) -> List[QueryMetrics]:
        """Get queries that took longer than threshold."""
        with self.lock:
            slow_queries = [
                q for q in self.query_history 
                if q.total_time_ms > threshold_ms
            ]
            # Sort by total time descending
            slow_queries.sort(key=lambda x: x.total_time_ms, reverse=True)
            return slow_queries[:limit]
    
    def reset_metrics(self) -> None:
        """Reset all metrics."""
        with self.lock:
            self.query_history.clear()
            self.total_queries = 0
            self.successful_queries = 0
            self.failed_queries = 0
            self.cache_hits = 0
            self.retrieval_times.clear()
            self.generation_times.clear()
            self.total_times.clear()
            self.strategy_counts.clear()
            self.model_counts.clear()
            self.error_counts.clear()
            self.recent_errors.clear()
            logger.info("Metrics reset")


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector