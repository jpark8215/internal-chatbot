from fastapi import FastAPI
import time
from importlib.util import find_spec
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .local_model import get_local_llm, ModelNotFoundError, GenerationError
from .models import GenerateRequest, GenerateResponse, HealthResponse
from .config import get_settings
from .dao import get_dao
from .embeddings import embed_texts
from .ingest_files import ingest_path
from .logging_config import setup_logging, get_logger, log_request, log_llm_request, set_correlation_id
from .query_history_dao import get_query_history_dao, QueryRecord
from .file_watcher import start_file_monitoring, stop_file_monitoring
import threading
from pathlib import Path as _Path
import uuid

app = FastAPI(title="Internal Chatbot API")
settings = get_settings()

# Setup logging
setup_logging(settings.log_level, settings.log_format)

# Middleware removed for simplicity - can be re-added if needed

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

logger = get_logger(__name__)


@app.on_event("startup")
async def _startup():
    """Application startup event."""
    # Auto-ingest if configured
    settings_local = get_settings()
    if settings_local.auto_ingest_on_start and (settings_local.database_url or settings_local.db_host):
        target = settings_local.auto_ingest_path
        if target and _Path(target).exists():
            try:
                # Allow ingesting additional files even if database has content
                # dao = get_dao()
                # if dao.count_documents() > 0:
                #     return
                pass
            except Exception:
                return

            def _run():
                try:
                    total = ingest_path(_Path(target))
                    logger.info(f"[auto-ingest] Ingested {total} chunks from {target}")
                except Exception as e:
                    logger.error(f"[auto-ingest] Failed: {e}")

            t = threading.Thread(target=_run, daemon=True)
            t.start()
        # Start file monitoring if enabled
        if settings_local.auto_ingest_watch_mode:
            try:
                start_file_monitoring()
                logger.info("[startup] File monitoring started")
            except Exception as e:
                logger.error(f"[startup] Failed to start file monitoring: {e}")

@app.on_event("shutdown")
async def _shutdown():
    """Application shutdown event."""
    llm = get_local_llm()
    try:
        await llm.close()
    except Exception:
        pass

    # Close database connection pool
    try:
        dao = get_dao()
        dao.close_pool()
    except Exception:
        pass

    # Stop file monitoring
    try:
        stop_file_monitoring()
    except Exception:
        pass

@app.get("/health", response_model=HealthResponse)
async def health():
    """Check the health of API components."""
    db_status = "disabled"  # Default to disabled

    if settings.db_host and find_spec("psycopg2"):
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=settings.db_host,
                port=settings.db_port,
                dbname=settings.db_name,
                user=settings.db_user,
                password=settings.db_password
            )
            conn.close()
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {str(e)}"

    llm = get_local_llm()
    try:
        # Check if default model exists
        models = await llm.get_models()
        llm_status = "available" if settings.default_model in models else "model-missing"
    except Exception:
        llm_status = "unavailable"

    return HealthResponse(
        status="ok",
        db=db_status,
        local_llm=llm_status
    )


# Detailed health endpoint removed for simplicity


@app.get("/")
async def root():
    """Serve chat UI if present; otherwise show basic API info."""
    index_path = _static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "message": "Internal chatbot API",
        "docs": "/docs",
        "health": "/health",
        "history": "/history"
    }


@app.get("/history")
async def history_page():
    """Serve query history page."""
    history_path = _static_dir / "history.html"
    if history_path.exists():
        return FileResponse(str(history_path))
    return {"message": "History page not found"}

@app.get("/admin")
async def admin_panel():
    """Serve admin panel (hidden from main UI)."""
    admin_path = _static_dir / "admin.html"
    if admin_path.exists():
        return FileResponse(str(admin_path))
    return {"message": "Admin panel not found"}

@app.get("/info")
async def info():
    """Get API capabilities and configuration info."""
    llm = get_local_llm()
    try:
        models = await llm.get_models()
        return {
            "app": "internal-chatbot",
            "models": models,
            "default_model": settings.default_model,
            "features": {
                "chat": True,
                "streaming": settings.enable_streaming,
                "conversation_memory": settings.enable_conversation_memory,
                "hybrid_search": settings.enable_hybrid_search
            }
        }
    except Exception as e:
        return {
            "app": "internal-chatbot",
            "error": str(e),
            "features": {
                "chat": False,
                "streaming": False,
                "conversation_memory": False,
                "hybrid_search": False
            }
        }


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate text using the enhanced RAG service."""
    request_start_time = time.time()
    correlation_id = str(uuid.uuid4())[:8]
    set_correlation_id(correlation_id)

    # Import here to avoid circular imports
    from .rag_service import get_rag_service
    from .response_cache import get_response_cache
    from .metrics import get_metrics_collector, QueryMetrics

    # Initialize services
    rag_service = get_rag_service()
    cache = get_response_cache()
    metrics_collector = get_metrics_collector()
    query_history_dao = get_query_history_dao()

    # Initialize query logging
    query_record = QueryRecord(
        session_id=correlation_id,
        query_text=req.prompt,
        model_used=settings.default_model
    )
    
    def log_query_once(success: bool, response_text: str = "", sources: list = None, 
                      error_message: str = None, total_time_ms: int = 0):
        """Log query history only once per request."""
        query_record.success = success
        query_record.response_text = response_text
        query_record.sources_used = sources
        query_record.error_message = error_message
        query_record.response_time_ms = total_time_ms
        try:
            query_history_dao.log_query(query_record)
        except Exception as log_error:
            logger.warning(f'Failed to log query: {log_error}')

    try:
        # Check cache first
        cached_response = cache.get(req.prompt, req.system_prompt, settings.default_model)
        if cached_response:
            total_duration = time.time() - request_start_time
            
            # Log cache hit
            logger.info(f"Cache hit for query: {req.prompt[:50]}...", extra={"correlation_id": correlation_id})
            
            # Record metrics
            query_metrics = QueryMetrics(
                query_id=correlation_id,
                query_text=req.prompt,
                timestamp=request_start_time,
                retrieval_time_ms=0,
                generation_time_ms=0,
                total_time_ms=total_duration * 1000,
                documents_retrieved=len(cached_response.sources),
                strategy_used="cache",
                model_used=cached_response.model_used,
                success=True,
                cache_hit=True
            )
            metrics_collector.record_query(query_metrics)
            
            # Log query history
            log_query_once(
                success=True,
                response_text=cached_response.text,
                sources=cached_response.sources,
                total_time_ms=int(total_duration * 1000)
            )
            
            return GenerateResponse(
                ok=True,
                text=cached_response.text,
                model=cached_response.model_used,
                sources=cached_response.sources
            )

        # Generate response using RAG service
        logger.info(f"Processing query: {req.prompt[:100]}...", extra={"correlation_id": correlation_id})
        
        rag_response = await rag_service.generate_response(
            query=req.prompt,
            user_system_prompt=req.system_prompt,
            top_k=5
        )

        if rag_response.success:
            # Cache successful response
            cache.put(
                query=req.prompt,
                response_text=rag_response.text,
                sources=rag_response.sources,
                model_used=rag_response.model_used,
                system_prompt=req.system_prompt
            )
            
            # Record metrics
            query_metrics = QueryMetrics(
                query_id=correlation_id,
                query_text=req.prompt,
                timestamp=request_start_time,
                retrieval_time_ms=rag_response.retrieval_result.retrieval_time_ms,
                generation_time_ms=rag_response.generation_time_ms,
                total_time_ms=rag_response.total_time_ms,
                documents_retrieved=len(rag_response.sources),
                strategy_used=rag_response.retrieval_result.strategy_used.value,
                model_used=rag_response.model_used,
                success=True
            )
            metrics_collector.record_query(query_metrics)
            
            # Log query history
            log_query_once(
                success=True,
                response_text=rag_response.text,
                sources=rag_response.sources,
                total_time_ms=int(rag_response.total_time_ms)
            )

            return GenerateResponse(
                ok=True,
                text=rag_response.text,
                model=rag_response.model_used,
                sources=rag_response.sources
            )
        else:
            # Handle failed response
            query_metrics = QueryMetrics(
                query_id=correlation_id,
                query_text=req.prompt,
                timestamp=request_start_time,
                retrieval_time_ms=rag_response.retrieval_result.retrieval_time_ms,
                generation_time_ms=rag_response.generation_time_ms,
                total_time_ms=rag_response.total_time_ms,
                documents_retrieved=len(rag_response.sources),
                strategy_used=rag_response.retrieval_result.strategy_used.value,
                model_used=rag_response.model_used,
                success=False,
                error_message=rag_response.error_message
            )
            metrics_collector.record_query(query_metrics)
            
            # Log failed query
            log_query_once(
                success=False,
                error_message=rag_response.error_message,
                sources=rag_response.sources,
                total_time_ms=int(rag_response.total_time_ms)
            )

            return GenerateResponse(
                ok=False,
                reason=rag_response.error_message or "Generation failed",
                sources=rag_response.sources
            )

    except Exception as e:
        total_duration = time.time() - request_start_time
        logger.error(f"Unexpected error in generate endpoint: {e}", extra={"correlation_id": correlation_id})
        
        # Record error metrics
        query_metrics = QueryMetrics(
            query_id=correlation_id,
            query_text=req.prompt,
            timestamp=request_start_time,
            retrieval_time_ms=0,
            generation_time_ms=0,
            total_time_ms=total_duration * 1000,
            documents_retrieved=0,
            strategy_used="error",
            model_used=settings.default_model,
            success=False,
            error_message=str(e)
        )
        metrics_collector.record_query(query_metrics)
        
        # Log failed query
        log_query_once(
            success=False,
            error_message=f"Unexpected error: {str(e)}",
            total_time_ms=int(total_duration * 1000)
        )
        
        return GenerateResponse(
            ok=False,
            reason=f"Unexpected error: {str(e)}",
            sources=None
        )


@app.get("/debug/database")
async def debug_database():
    """Debug database connection and document count."""
    try:
        dao = get_dao()
        total_docs = dao.count_documents()
        docs_by_source = dao.count_documents_by_source()

        return {
            "status": "connected",
            "total_documents": total_docs,
            "documents_by_source": docs_by_source,
            "database_url_configured": bool(settings.database_url),
            "db_host_configured": bool(settings.db_host),
            "auto_ingest_path": settings.auto_ingest_path,
            "auto_ingest_enabled": settings.auto_ingest_on_start
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "database_url_configured": bool(settings.database_url),
            "db_host_configured": bool(settings.db_host),
            "auto_ingest_path": settings.auto_ingest_path,
            "auto_ingest_enabled": settings.auto_ingest_on_start
        }


@app.get("/debug/search")
async def debug_search(query: str = "OMH Harp program admission criteria"):
    """Debug search functionality."""
    try:
        vectors = await embed_texts([query])
        query_vec = vectors[0]
        dao = get_dao()

        if settings.enable_hybrid_search:
            matches = dao.search_hybrid(query_vec, query, top_k=5)
        else:
            matches = dao.search_combined(query_vec, query, top_k=5)

        return {
            "query": query,
            "embedding_dimension": len(query_vec),
            "matches_found": len(matches),
            "matches": [
                {
                    "id": doc_id,
                    "source_file": source_file,
                    "score": float(score),
                    "content_preview": content[:200] + "..." if len(content) > 200 else content
                }
                for doc_id, content, score, source_file in matches
            ]
        }
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.get("/debug/keyword-search")
async def debug_keyword_search(query: str = "recovery-oriented"):
    """Debug keyword search functionality."""
    try:
        dao = get_dao()
        matches = dao.search_keyword(query, top_k=10)

        return {
            "query": query,
            "search_type": "keyword",
            "matches_found": len(matches),
            "matches": [
                {
                    "id": doc_id,
                    "source_file": source_file,
                    "score": float(score),
                    "content_preview": content[:300] + "..." if len(content) > 300 else content
                }
                for doc_id, content, score, source_file in matches
            ]
        }
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "error_type": type(e).__name__
        }


# Configuration validation endpoints removed for simplicity


@app.get("/stats")
async def get_stats():
    """Get application statistics."""
    try:
        dao = get_dao()
        total_docs = dao.count_documents()
        docs_by_source = dao.count_documents_by_source()

        # Statistics retrieved successfully

        return {
            "total_documents": total_docs,
            "documents_by_source": docs_by_source,
            "features_enabled": {
                "streaming": settings.enable_streaming,
                "conversation_memory": settings.enable_conversation_memory,
                "hybrid_search": settings.enable_hybrid_search
            }
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"error": str(e)}

# Query History API Endpoints
from fastapi import Query
from typing import Optional

@app.get("/api/history")
async def get_query_history(
    limit: int = Query(50, ge=1, le=100),
    session_id: Optional[str] = Query(None)
):
    """Get recent query history."""
    try:
        query_history_dao = get_query_history_dao()
        queries = query_history_dao.get_recent_queries(limit=limit, session_id=session_id)
        
        return {
            "queries": [
                {
                    "id": q.id,
                    "query_text": q.query_text,
                    "response_text": q.response_text,
                    "sources_used": q.sources_used,
                    "search_type": q.search_type,
                    "response_time_ms": q.response_time_ms,
                    "success": q.success,
                    "created_at": q.created_at.isoformat() if q.created_at else None
                }
                for q in queries
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get query history: {e}")
        return {"error": str(e)}

@app.get("/api/analytics")
async def get_query_analytics(days: int = Query(30, ge=1, le=365)):
    """Get query analytics."""
    try:
        query_history_dao = get_query_history_dao()
        analytics = query_history_dao.get_query_analytics(days=days)
        usage_stats = query_history_dao.get_usage_stats(days=days)
        
        return {
            "usage_stats": usage_stats,
            "top_queries": analytics
        }
    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        return {"error": str(e)}

@app.get("/api/search-history")
async def search_query_history(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50)
):
    """Search query history."""
    try:
        query_history_dao = get_query_history_dao()
        results = query_history_dao.search_queries(q, limit=limit)
        
        return {
            "results": [
                {
                    "id": r.id,
                    "query_text": r.query_text,
                    "response_text": r.response_text,
                    "created_at": r.created_at.isoformat() if r.created_at else None
                }
                for r in results
            ]
        }
    except Exception as e:
        logger.error(f"Failed to search history: {e}")
        return {"error": str(e)}

# Performance and Monitoring Endpoints

@app.get("/api/metrics")
async def get_system_metrics(time_window: int = Query(60, ge=1, le=1440)):
    """Get system performance metrics."""
    try:
        from .metrics import get_metrics_collector
        metrics_collector = get_metrics_collector()
        system_metrics = metrics_collector.get_system_metrics(time_window_minutes=time_window)
        
        return {
            "time_window_minutes": time_window,
            "metrics": {
                "total_queries": system_metrics.total_queries,
                "successful_queries": system_metrics.successful_queries,
                "failed_queries": system_metrics.failed_queries,
                "cache_hits": system_metrics.cache_hits,
                "performance": {
                    "avg_retrieval_time_ms": system_metrics.avg_retrieval_time_ms,
                    "avg_generation_time_ms": system_metrics.avg_generation_time_ms,
                    "avg_total_time_ms": system_metrics.avg_total_time_ms,
                    "p95_total_time_ms": system_metrics.p95_total_time_ms,
                    "p99_total_time_ms": system_metrics.p99_total_time_ms
                },
                "rates": {
                    "queries_per_minute": system_metrics.queries_per_minute,
                    "error_rate": system_metrics.error_rate,
                    "cache_hit_rate": system_metrics.cache_hit_rate
                },
                "distribution": {
                    "strategies": system_metrics.strategy_distribution,
                    "models": system_metrics.model_distribution
                }
            }
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        return {"error": str(e)}

@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get response cache statistics."""
    try:
        from .response_cache import get_response_cache
        cache = get_response_cache()
        return cache.get_stats()
    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        return {"error": str(e)}

@app.post("/api/cache/clear")
async def clear_cache():
    """Clear the response cache."""
    try:
        from .response_cache import get_response_cache
        cache = get_response_cache()
        cache.clear()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return {"error": str(e)}

@app.get("/api/errors/recent")
async def get_recent_errors(limit: int = Query(10, ge=1, le=50)):
    """Get recent system errors."""
    try:
        from .metrics import get_metrics_collector
        metrics_collector = get_metrics_collector()
        recent_errors = metrics_collector.get_recent_errors(limit=limit)
        return {"errors": recent_errors}
    except Exception as e:
        logger.error(f"Failed to get recent errors: {e}")
        return {"error": str(e)}

@app.get("/api/queries/slow")
async def get_slow_queries(threshold_ms: float = Query(5000, ge=1000), limit: int = Query(10, ge=1, le=50)):
    """Get slow queries above threshold."""
    try:
        from .metrics import get_metrics_collector
        metrics_collector = get_metrics_collector()
        slow_queries = metrics_collector.get_slow_queries(threshold_ms=threshold_ms, limit=limit)
        
        return {
            "threshold_ms": threshold_ms,
            "slow_queries": [
                {
                    "query_id": q.query_id,
                    "query_text": q.query_text[:100] + "..." if len(q.query_text) > 100 else q.query_text,
                    "total_time_ms": q.total_time_ms,
                    "retrieval_time_ms": q.retrieval_time_ms,
                    "generation_time_ms": q.generation_time_ms,
                    "strategy_used": q.strategy_used,
                    "timestamp": q.timestamp
                }
                for q in slow_queries
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get slow queries: {e}")
        return {"error": str(e)}