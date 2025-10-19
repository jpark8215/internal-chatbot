from fastapi import FastAPI, Query
import time
from importlib.util import find_spec
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, List, Dict, Any

from .local_model import get_local_llm, ModelNotFoundError, GenerationError
from .models import GenerateRequest, GenerateResponse, HealthResponse
from .config import get_settings
from .dao import get_dao
from .embeddings import embed_texts
from .ingest_files import ingest_path
from .logging_config import setup_logging, get_logger, log_request, log_llm_request, set_correlation_id
from .query_history_dao import get_query_history_dao, QueryRecord
from .file_watcher import start_file_monitoring, stop_file_monitoring
from .scheduled_cleanup import start_scheduled_cleanup, stop_scheduled_cleanup
import threading
from pathlib import Path as _Path
import uuid
from datetime import datetime, timedelta

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
                success = start_file_monitoring()
                if success:
                    logger.info("[startup] File monitoring started successfully")
                else:
                    logger.warning("[startup] File monitoring failed to start - check configuration")
            except Exception as e:
                logger.error(f"[startup] Failed to start file monitoring: {e}")
                # Try to start periodic checker as fallback
                try:
                    from .file_watcher import PeriodicFileChecker
                    logger.info("[startup] Attempting to start periodic file checker as fallback")
                    checker = PeriodicFileChecker()
                    if checker.start():
                        logger.info("[startup] Periodic file checker started as fallback")
                except Exception as fallback_error:
                    logger.error(f"[startup] Fallback file checker also failed: {fallback_error}")
        
        # Start scheduled cleanup service if enabled
        if settings_local.enable_scheduled_cleanup:
            try:
                cleanup_success = start_scheduled_cleanup(cleanup_interval=settings_local.cleanup_interval)
                if cleanup_success:
                    logger.info(f"[startup] Scheduled cleanup service started (interval: {settings_local.cleanup_interval}s)")
                else:
                    logger.warning("[startup] Scheduled cleanup service failed to start")
            except Exception as e:
                logger.error(f"[startup] Failed to start scheduled cleanup service: {e}")
        else:
            logger.info("[startup] Scheduled cleanup service disabled in configuration")
    


@app.on_event("shutdown")
async def _shutdown():
    """Application shutdown event."""
    # Stop scheduled cleanup
    try:
        stop_scheduled_cleanup()
        logger.info("[shutdown] Scheduled cleanup service stopped")
    except Exception as e:
        logger.error(f"[shutdown] Error stopping scheduled cleanup: {e}")
    
    # Stop file monitoring
    try:
        stop_file_monitoring()
        logger.info("[shutdown] File monitoring stopped")
    except Exception as e:
        logger.error(f"[shutdown] Error stopping file monitoring: {e}")
    
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

    # Check if database is configured (either DATABASE_URL or db_host)
    if (settings.database_url or settings.db_host) and find_spec("psycopg2"):
        try:
            # Use the DAO to test the connection (it handles both DATABASE_URL and individual settings)
            dao = get_dao()
            count = dao.count_documents()
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

@app.get("/feedback-dashboard")
async def feedback_dashboard():
    """Serve comprehensive feedback dashboard page."""
    feedback_path = _static_dir / "feedback-dashboard.html"
    if feedback_path.exists():
        return FileResponse(str(feedback_path))
    return {"message": "Feedback dashboard not found"}



@app.get("/monitoring-dashboard")
async def monitoring_dashboard():
    """Serve monitoring dashboard page."""
    monitoring_path = _static_dir / "monitoring-dashboard.html"
    if monitoring_path.exists():
        return FileResponse(str(monitoring_path))
    return {"message": "Monitoring dashboard not found"}





# Admin HTML Pages


@app.get("/admin/system")
async def system_dashboard():
    """Serve consolidated system dashboard with health, debug, and stats."""
    # Try to serve a consolidated dashboard, fallback to admin panel
    system_path = _static_dir / "system-dashboard.html"
    if system_path.exists():
        return FileResponse(str(system_path))
    
    # Fallback to admin panel if consolidated dashboard doesn't exist
    admin_path = _static_dir / "admin.html"
    if admin_path.exists():
        return FileResponse(str(admin_path))
    
    return {"message": "System dashboard not found"}

@app.get("/admin/debug")
async def debug_dashboard():
    """Serve comprehensive debug dashboard."""
    debug_path = _static_dir / "debug-dashboard.html"
    if debug_path.exists():
        return FileResponse(str(debug_path))
    return {"message": "Debug dashboard not found"}


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
                sources=cached_response.sources,
                search_strategy="cache"
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

            # Include quality indicators and search strategy in the response
            response_data = {
                "ok": True,
                "text": rag_response.text,
                "model": rag_response.model_used,
                "sources": rag_response.sources,
                "search_strategy": rag_response.retrieval_result.strategy_used.value
            }
            
            # Add quality indicators if available
            if rag_response.quality_indicators:
                response_data["quality_indicators"] = rag_response.quality_indicators
            
            return GenerateResponse(**response_data)
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
                sources=rag_response.sources,
                search_strategy=rag_response.retrieval_result.strategy_used.value if rag_response.retrieval_result else None
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


@app.get("/api/system-health")
async def get_system_health():
    """Get comprehensive system health including database, file monitoring, and system resources."""
    try:
        from .file_watcher import is_file_monitoring_active
        from pathlib import Path
        import psutil
        import os
        
        dao = get_dao()
        
        # Database health
        db_health = {"status": "unknown"}
        try:
            total_docs = dao.count_documents()
            docs_by_source = dao.count_documents_by_source()
            db_health = {
                "status": "healthy",
                "total_documents": total_docs,
                "unique_sources": len(docs_by_source),
                "documents_by_source": docs_by_source[:10],  # First 10 for overview
                "connection": "ok",
                "database_url_configured": bool(settings.database_url),
                "db_host_configured": bool(settings.db_host)
            }
        except Exception as e:
            db_health = {
                "status": "error",
                "error": str(e),
                "database_url_configured": bool(settings.database_url),
                "db_host_configured": bool(settings.db_host)
            }
        
        # File monitoring health
        monitoring_health = {
            "enabled": settings.auto_ingest_watch_mode,
            "active": is_file_monitoring_active(),
            "watch_interval": settings.auto_ingest_watch_interval,
            "auto_ingest_on_start": settings.auto_ingest_on_start
        }
        
        # Auto-ingest path health
        path_health = {"configured": False}
        if settings.auto_ingest_path:
            ingest_path = Path(settings.auto_ingest_path)
            path_health = {
                "configured": True,
                "path": settings.auto_ingest_path,
                "exists": ingest_path.exists(),
                "readable": False,
                "file_count": 0
            }
            
            if ingest_path.exists():
                try:
                    # Test readability
                    list(ingest_path.iterdir())
                    path_health["readable"] = True
                    
                    # Count files
                    for ext in ['.pdf', '.docx', '.txt', '.md', '.markdown']:
                        path_health["file_count"] += len(list(ingest_path.rglob(f'*{ext}')))
                except Exception as e:
                    path_health["error"] = str(e)
        
        # System resources
        system_health = {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:').percent,
            "process_count": len(psutil.pids())
        }
        
        # Overall health assessment
        issues = []
        if db_health["status"] != "healthy":
            issues.append("Database connection issues")
        if monitoring_health["enabled"] and not monitoring_health["active"]:
            issues.append("File monitoring not active")
        if path_health["configured"] and not path_health.get("exists", False):
            issues.append("Auto-ingest path does not exist")
        if path_health.get("exists", False) and not path_health.get("readable", False):
            issues.append("Auto-ingest path not readable")
        if system_health["memory_percent"] > 90:
            issues.append("High memory usage")
        if system_health["cpu_percent"] > 90:
            issues.append("High CPU usage")
        
        overall_status = "healthy" if not issues else "degraded" if len(issues) <= 2 else "critical"
        
        return {
            "overall_status": overall_status,
            "issues": issues,
            "components": {
                "database": db_health,
                "file_monitoring": monitoring_health,
                "auto_ingest_path": path_health,
                "system_resources": system_health
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        return {
            "overall_status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/debug/search")
async def debug_search_comprehensive(
    query: str = Query("policy", description="Search query to test"),
    search_type: str = Query("all", regex="^(all|keyword|semantic|hybrid)$", description="Type of search to test")
):
    """Comprehensive search debugging endpoint."""
    try:
        dao = get_dao()
        results = {
            "query": query,
            "total_docs_in_db": dao.count_documents(),
            "search_types_tested": []
        }
        
        # Test keyword search
        if search_type in ["all", "keyword"]:
            try:
                keyword_results = dao.search_keyword(query, top_k=5)
                results["keyword_search"] = {
                    "success": True,
                    "results_count": len(keyword_results),
                    "results": [
                        {
                            "id": doc_id,
                            "score": float(score),
                            "content_preview": content[:200] + "..." if len(content) > 200 else content,
                            "source": source_file
                        }
                        for doc_id, content, score, source_file in keyword_results[:3]
                    ]
                }
                results["search_types_tested"].append("keyword")
            except Exception as e:
                results["keyword_search"] = {"success": False, "error": str(e)}
        
        # Test semantic search
        if search_type in ["all", "semantic"]:
            try:
                vectors = await embed_texts([query])
                if vectors:
                    semantic_results = dao.search(vectors[0], top_k=5)
                    results["semantic_search"] = {
                        "success": True,
                        "embedding_dimension": len(vectors[0]),
                        "results_count": len(semantic_results),
                        "results": [
                            {
                                "id": doc_id,
                                "score": float(score),
                                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                                "source": source_file
                            }
                            for doc_id, content, score, source_file in semantic_results[:3]
                        ]
                    }
                    results["search_types_tested"].append("semantic")
                else:
                    results["semantic_search"] = {"success": False, "error": "No embeddings generated"}
            except Exception as e:
                results["semantic_search"] = {"success": False, "error": str(e)}
        
        # Test hybrid search if enabled
        if search_type in ["all", "hybrid"] and settings.enable_hybrid_search:
            try:
                vectors = await embed_texts([query])
                if vectors:
                    hybrid_results = dao.search_hybrid(vectors[0], query, top_k=5)
                    results["hybrid_search"] = {
                        "success": True,
                        "results_count": len(hybrid_results),
                        "results": [
                            {
                                "id": doc_id,
                                "score": float(score),
                                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                                "source": source_file
                            }
                            for doc_id, content, score, source_file in hybrid_results[:3]
                        ]
                    }
                    results["search_types_tested"].append("hybrid")
            except Exception as e:
                results["hybrid_search"] = {"success": False, "error": str(e)}
        
        return results
        
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.get("/debug/file-monitoring")
async def debug_file_monitoring():
    """Debug file monitoring system status and sync issues."""
    try:
        from .file_watcher import is_file_monitoring_active
        from .file_cleanup import get_database_file_status, cleanup_orphaned_documents
        from .scheduled_cleanup import is_scheduled_cleanup_active, get_cleanup_service_status
        from pathlib import Path
        
        settings = get_settings()
        dao = get_dao()
        
        # Check file monitoring status
        monitoring_active = is_file_monitoring_active()
        
        # Check auto-ingest path
        auto_ingest_path = settings.auto_ingest_path
        path_exists = False
        path_readable = False
        file_count = 0
        
        if auto_ingest_path:
            ingest_path = Path(auto_ingest_path)
            path_exists = ingest_path.exists()
            if path_exists:
                try:
                    path_readable = True
                    # Count supported files
                    for ext in ['.pdf', '.docx', '.txt', '.md', '.markdown']:
                        file_count += len(list(ingest_path.rglob(f'*{ext}')))
                except Exception:
                    path_readable = False
        
        # Get database vs filesystem sync status
        sync_status = {}
        if auto_ingest_path and path_exists:
            try:
                sync_status = get_database_file_status(Path(auto_ingest_path))
            except Exception as e:
                sync_status = {"error": str(e)}
        
        # Get database document count
        total_docs = dao.count_documents()
        docs_by_source = dao.count_documents_by_source()
        
        # Get cleanup service status
        cleanup_active = is_scheduled_cleanup_active()
        cleanup_status = get_cleanup_service_status()
        
        return {
            "file_monitoring": {
                "enabled_in_config": settings.auto_ingest_watch_mode,
                "currently_active": monitoring_active,
                "watch_interval_seconds": settings.auto_ingest_watch_interval,
                "status": "active" if monitoring_active else "inactive"
            },
            "scheduled_cleanup": {
                "enabled_in_config": settings.enable_scheduled_cleanup,
                "currently_active": cleanup_active,
                "cleanup_interval_seconds": cleanup_status.get("interval"),
                "status": cleanup_status.get("message", "unknown")
            },
            "auto_ingest_path": {
                "configured_path": auto_ingest_path,
                "path_exists": path_exists,
                "path_readable": path_readable,
                "supported_files_count": file_count
            },
            "database_status": {
                "total_documents": total_docs,
                "unique_source_files": len(docs_by_source),
                "documents_by_source": docs_by_source[:10]  # Show first 10
            },
            "sync_analysis": sync_status,
            "diagnosis": _diagnose_file_monitoring_issues(
                monitoring_active, 
                settings.auto_ingest_watch_mode,
                path_exists,
                path_readable,
                file_count,
                total_docs,
                sync_status
            )
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "error_type": type(e).__name__
        }


@app.post("/debug/sync-filesystem")
async def sync_filesystem():
    """Manually sync database with filesystem and clean up orphaned documents."""
    try:
        from .file_cleanup import cleanup_orphaned_documents, sync_database_with_filesystem
        from pathlib import Path
        
        settings = get_settings()
        
        if not settings.auto_ingest_path:
            return {"error": "No auto-ingest path configured"}
        
        ingest_path = Path(settings.auto_ingest_path)
        if not ingest_path.exists():
            return {"error": f"Auto-ingest path does not exist: {ingest_path}"}
        
        # Step 1: Clean up orphaned documents
        removed_count, removed_files, cache_invalidated = cleanup_orphaned_documents(ingest_path)
        
        # Step 2: Get comprehensive sync status
        sync_results = sync_database_with_filesystem(ingest_path)
        
        return {
            "success": True,
            "cleanup_results": {
                "orphaned_documents_removed": removed_count,
                "orphaned_files": removed_files,
                "cache_entries_invalidated": cache_invalidated
            },
            "sync_results": sync_results,
            "message": f"Cleaned up {removed_count} orphaned documents from {len(removed_files)} files"
        }
        
    except Exception as e:
        logger.error(f"Failed to sync filesystem: {e}")
        return {"error": str(e)}


@app.post("/debug/restart-file-monitoring")
async def restart_file_monitoring():
    """Restart the file monitoring system."""
    try:
        from .file_watcher import stop_file_monitoring, start_file_monitoring, is_file_monitoring_active
        
        # Stop current monitoring
        stop_file_monitoring()
        
        # Wait a moment
        import time
        time.sleep(1)
        
        # Start monitoring
        success = start_file_monitoring()
        
        # Check if it's running
        is_active = is_file_monitoring_active()
        
        return {
            "success": success,
            "monitoring_active": is_active,
            "message": "File monitoring restarted successfully" if success else "Failed to restart file monitoring"
        }
        
    except Exception as e:
        return {"error": str(e), "success": False}


@app.post("/debug/restart-cleanup-service")
async def restart_cleanup_service():
    """Restart the scheduled cleanup service."""
    try:
        from .scheduled_cleanup import stop_scheduled_cleanup, start_scheduled_cleanup, get_cleanup_service_status
        
        settings = get_settings()
        
        # Stop current service
        stop_scheduled_cleanup()
        
        # Wait a moment
        import time
        time.sleep(1)
        
        # Start service if enabled
        if settings.enable_scheduled_cleanup:
            success = start_scheduled_cleanup(cleanup_interval=settings.cleanup_interval)
            status = get_cleanup_service_status()
            
            return {
                "success": success,
                "service_active": status.get("active", False),
                "cleanup_interval": status.get("interval"),
                "message": f"Cleanup service restarted successfully (interval: {settings.cleanup_interval}s)" if success else "Failed to restart cleanup service"
            }
        else:
            return {
                "success": False,
                "service_active": False,
                "message": "Cleanup service is disabled in configuration"
            }
            
    except Exception as e:
        return {"error": str(e), "success": False}


@app.post("/debug/run-cleanup-now")
async def run_cleanup_now():
    """Manually trigger orphaned document cleanup."""
    try:
        from .file_cleanup import cleanup_orphaned_documents
        from pathlib import Path
        
        settings = get_settings()
        
        if not settings.auto_ingest_path:
            return {"error": "No auto-ingest path configured", "success": False}
        
        base_path = Path(settings.auto_ingest_path)
        if not base_path.exists():
            return {"error": f"Auto-ingest path does not exist: {base_path}", "success": False}
        
        # Run cleanup
        removed_count, removed_files, cache_invalidated = cleanup_orphaned_documents(base_path)
        
        return {
            "success": True,
            "orphaned_documents_removed": removed_count,
            "orphaned_files": [Path(f).name for f in removed_files],
            "cache_entries_invalidated": cache_invalidated,
            "message": f"Cleaned up {removed_count} orphaned documents from {len(removed_files)} files"
        }
        
    except Exception as e:
        logger.error(f"Failed to restart file monitoring: {e}")
        return {"error": str(e)}


@app.get("/debug/rag-flow")
async def debug_rag_flow(query: str = "test query"):
    """Debug the complete RAG flow to identify issues."""
    try:
        from .rag_service import get_rag_service
        from .embeddings import embed_texts
        
        rag_service = get_rag_service()
        dao = get_dao()
        
        # Step 1: Check document count
        doc_count = dao.count_documents()
        
        # Step 2: Test embedding generation
        embedding_error = None
        try:
            vectors = await embed_texts([query])
            embedding_success = True
            embedding_dim = len(vectors[0]) if vectors else 0
        except Exception as e:
            embedding_success = False
            embedding_error = str(e)
            embedding_dim = 0
        
        # Step 3: Test document retrieval
        retrieval_error = None
        try:
            retrieval_result = await rag_service.retrieve_documents(query, top_k=5)
            retrieval_success = True
            documents_found = len(retrieval_result.documents)
            strategy_used = retrieval_result.strategy_used.value
        except Exception as e:
            retrieval_success = False
            retrieval_error = str(e)
            documents_found = 0
            strategy_used = "error"
        
        # Step 4: Test context building
        context_error = None
        try:
            if retrieval_success and retrieval_result.documents:
                context_text, sources = rag_service._build_context(retrieval_result.documents, query)
                context_success = True
                context_length = len(context_text)
                sources_count = len(sources)
            else:
                context_success = False
                context_length = 0
                sources_count = 0
                context_text = ""
        except Exception as e:
            context_success = False
            context_error = str(e)
            context_length = 0
            sources_count = 0
            context_text = ""
        
        return {
            "query": query,
            "debug_results": {
                "database": {
                    "total_documents": doc_count,
                    "status": "ok" if doc_count > 0 else "no_documents"
                },
                "embedding": {
                    "success": embedding_success,
                    "dimension": embedding_dim,
                    "error": embedding_error if not embedding_success else None
                },
                "retrieval": {
                    "success": retrieval_success,
                    "documents_found": documents_found,
                    "strategy_used": strategy_used,
                    "error": retrieval_error if not retrieval_success else None
                },
                "context_building": {
                    "success": context_success,
                    "context_length": context_length,
                    "sources_count": sources_count,
                    "has_context": len(context_text) > 0,
                    "error": context_error if not context_success else None
                }
            },
            "diagnosis": {
                "issue_found": not (embedding_success and retrieval_success and context_success and len(context_text) > 0),
                "likely_cause": _diagnose_rag_issue(doc_count, embedding_success, retrieval_success, context_success, len(context_text) if context_success else 0)
            }
        }
        
    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "error_type": type(e).__name__
        }


def _diagnose_rag_issue(doc_count, embedding_success, retrieval_success, context_success, context_length):
    """Diagnose the most likely cause of RAG issues."""
    if doc_count == 0:
        return "No documents in database - check auto-ingestion"
    elif not embedding_success:
        return "Embedding generation failed - check Ollama connection"
    elif not retrieval_success:
        return "Document retrieval failed - check database connection"
    elif not context_success:
        return "Context building failed - check document processing"
    elif context_length == 0:
        return "No relevant documents found - relevance threshold too strict or documents don't match query"
    else:
        return "No issues detected"


def _diagnose_file_monitoring_issues(monitoring_active, watch_mode_enabled, path_exists, path_readable, file_count, total_docs, sync_status):
    """Diagnose file monitoring and sync issues."""
    issues = []
    recommendations = []
    
    if not watch_mode_enabled:
        issues.append("File watching is disabled in configuration")
        recommendations.append("Set AUTO_INGEST_WATCH_MODE=true in .env file")
    
    if watch_mode_enabled and not monitoring_active:
        issues.append("File monitoring is enabled but not running")
        recommendations.append("Restart the application or use /debug/restart-file-monitoring endpoint")
    
    if not path_exists:
        issues.append("Auto-ingest path does not exist")
        recommendations.append("Check AUTO_INGEST_PATH in .env file and ensure directory exists")
    elif not path_readable:
        issues.append("Auto-ingest path is not readable")
        recommendations.append("Check directory permissions for the configured path")
    
    if file_count == 0 and path_exists:
        issues.append("No supported files found in auto-ingest directory")
        recommendations.append("Add .pdf, .docx, .txt, or .md files to the auto-ingest directory")
    
    if isinstance(sync_status, dict) and sync_status.get("sync_status") == "out_of_sync":
        orphaned_count = len(sync_status.get("orphaned_in_database", []))
        missing_count = len(sync_status.get("missing_from_database", []))
        
        if orphaned_count > 0:
            issues.append(f"{orphaned_count} files in database but not on filesystem")
            recommendations.append("Use /debug/sync-filesystem endpoint to clean up orphaned documents")
        
        if missing_count > 0:
            issues.append(f"{missing_count} files on filesystem but not in database")
            recommendations.append("Files may need to be re-ingested - check file monitoring or run manual ingestion")
    
    if not issues:
        return {
            "status": "healthy",
            "message": "File monitoring system appears to be working correctly"
        }
    else:
        return {
            "status": "issues_detected",
            "issues": issues,
            "recommendations": recommendations
        }


# Configuration validation endpoints removed for simplicity




# Query History API Endpoints

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

# User Feedback Endpoints
from pydantic import BaseModel

class FeedbackRequest(BaseModel):
    query_id: Optional[int] = None
    query_text: str
    response_text: str
    sources_used: Optional[List[Dict[str, Any]]] = None
    search_strategy: Optional[str] = None
    rating: Optional[int] = None
    is_accurate: Optional[bool] = None
    is_helpful: Optional[bool] = None
    missing_info: Optional[str] = None
    incorrect_info: Optional[str] = None
    preferred_sources: Optional[List[str]] = None
    comments: Optional[str] = None
    user_session: Optional[str] = None



@app.post("/api/feedback")
async def submit_feedback(feedback_req: FeedbackRequest):
    """Submit user feedback on RAG responses."""
    try:
        # Use clean feedback system to avoid syntax issues
        from .feedback_clean import get_clean_feedback_dao, SimpleFeedback
        
        feedback_dao = get_clean_feedback_dao()
        
        feedback = SimpleFeedback(
            query_text=feedback_req.query_text,
            response_text=feedback_req.response_text,
            sources_used=feedback_req.sources_used,
            search_strategy=feedback_req.search_strategy,
            rating=feedback_req.rating,
            is_accurate=feedback_req.is_accurate,
            is_helpful=feedback_req.is_helpful,
            missing_info=feedback_req.missing_info,
            incorrect_info=feedback_req.incorrect_info,
            comments=feedback_req.comments,
            user_session=feedback_req.user_session
        )
        
        feedback_id = feedback_dao.save_feedback(feedback)
        
        return {
            "success": True,
            "feedback_id": feedback_id,
            "message": "Thank you for your feedback! This helps improve our system."
        }
        
    except Exception as e:
        logger.error(f"Failed to save feedback: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/feedback/stats")
async def get_feedback_stats(days: int = Query(30, ge=1, le=365)):
    """Get feedback statistics."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        stats = feedback_dao.get_stats(days=days)
        
        return {
            "time_period_days": days,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback stats: {e}")
        return {"error": str(e)}

@app.get("/api/feedback/recent")
async def get_recent_feedback(limit: int = Query(10, ge=1, le=200)):
    """Get recent feedback entries."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        feedback_list = feedback_dao.get_recent_feedback(limit=limit)
        
        return {
            "feedback": feedback_list,
            "count": len(feedback_list)
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent feedback: {e}")
        return {"error": str(e)}

@app.get("/api/feedback/trends")
async def get_feedback_trends(days: int = Query(30, ge=1, le=365)):
    """Get feedback trend data for charts."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        trend_data = feedback_dao.get_trend_data(days=days)
        
        return {
            "time_period_days": days,
            "trend_data": trend_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback trends: {e}")
        return {"error": str(e)}

@app.get("/api/accuracy/analysis")
async def get_accuracy_analysis():
    """Get accuracy analysis and improvement recommendations."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        # Return basic accuracy analysis from clean feedback system
        stats = feedback_dao.get_stats(days=30)
        
        analysis = {
            "accuracy_score": stats.get("avg_rating", 0) / 5.0 if stats.get("avg_rating") else 0,
            "total_feedback": stats.get("total_feedback", 0),
            "accuracy_trend": "stable",  # Simplified for now
            "recommendations": [
                "Continue monitoring feedback patterns",
                "Focus on improving low-rated responses"
            ]
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to get accuracy analysis: {e}")
        return {"error": str(e)}

@app.get("/api/feedback/impact")
async def get_feedback_impact(days: int = Query(30, ge=1, le=365)):
    """Get feedback impact metrics and recent improvements."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        stats = feedback_dao.get_stats(days)
        
        # Get real impact metrics from database
        impact_data = {
            "total_feedback": stats.get("total_feedback", 0),
            "average_rating": stats.get("avg_rating", 0),
            "positive_feedback": 0,
            "improvements_made": 0,
            "response_quality_trend": "stable"
        }
        
        # Calculate real positive feedback and improvements
        try:
            with feedback_dao.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get positive feedback count (rating >= 4)
                    cur.execute("""
                        SELECT COUNT(*) 
                        FROM user_feedback 
                        WHERE rating >= 4 
                        AND created_at >= %s;
                    """, (datetime.now() - timedelta(days=days),))
                    
                    positive_count = cur.fetchone()[0] or 0
                    impact_data["positive_feedback"] = positive_count
                    
                    # Get real improvements count if table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'improvement_actions'
                        );
                    """)
                    
                    if cur.fetchone()[0]:
                        cur.execute("""
                            SELECT COUNT(*) 
                            FROM improvement_actions 
                            WHERE created_at >= %s;
                        """, (datetime.now() - timedelta(days=days),))
                        
                        improvements_count = cur.fetchone()[0] or 0
                        impact_data["improvements_made"] = improvements_count
                    
                    # Calculate trend based on recent vs older feedback
                    if days >= 14:  # Only calculate trend if we have enough data
                        cur.execute("""
                            SELECT AVG(rating) 
                            FROM user_feedback 
                            WHERE created_at >= %s AND created_at < %s;
                        """, (datetime.now() - timedelta(days=days//2), datetime.now()))
                        
                        recent_avg = cur.fetchone()[0]
                        
                        cur.execute("""
                            SELECT AVG(rating) 
                            FROM user_feedback 
                            WHERE created_at >= %s AND created_at < %s;
                        """, (datetime.now() - timedelta(days=days), datetime.now() - timedelta(days=days//2)))
                        
                        older_avg = cur.fetchone()[0]
                        
                        if recent_avg and older_avg:
                            if recent_avg > older_avg + 0.2:
                                impact_data["response_quality_trend"] = "improving"
                            elif recent_avg < older_avg - 0.2:
                                impact_data["response_quality_trend"] = "declining"
                            else:
                                impact_data["response_quality_trend"] = "stable"
                                
        except Exception as e:
            logger.error(f"Failed to calculate real impact metrics: {e}")
            # Keep basic stats even if detailed calculation fails
        
        return {
            "time_period_days": days,
            "impact_metrics": impact_data
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback impact: {e}")
        return {"error": str(e)}

@app.get("/api/feedback/recent-improvements")
async def get_recent_improvements(limit: int = Query(10, ge=1, le=50)):
    """Get recent improvements made based on user feedback."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        # Get real improvements from database
        feedback_dao = get_clean_feedback_dao()
        
        improvements = []
        try:
            with feedback_dao.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    # Check if improvement_actions table exists
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'improvement_actions'
                        );
                    """)
                    
                    table_exists = cur.fetchone()[0]
                    
                    if table_exists:
                        # Get real improvements from database
                        cur.execute("""
                            SELECT id, action_type, description, created_at, 
                                   COALESCE(status, 'implemented') as status
                            FROM improvement_actions 
                            ORDER BY created_at DESC 
                            LIMIT %s;
                        """, (limit,))
                        
                        rows = cur.fetchall()
                        
                        for row in rows:
                            improvements.append({
                                "id": row[0],
                                "action_type": row[1],
                                "description": row[2],
                                "created_at": row[3].isoformat() if row[3] else None,
                                "status": row[4]
                            })
                    
                    # If no improvements found, return empty list instead of synthetic data
                    if not improvements:
                        improvements = []
                        
        except Exception as e:
            logger.error(f"Failed to get real improvements: {e}")
            improvements = []
        
        return {
            "improvements": improvements
        }
        
    except Exception as e:
        logger.error(f"Failed to get recent improvements: {e}")
        return {"error": str(e)}

@app.get("/api/feedback/community-impact")
async def get_community_impact():
    """Get community feedback impact metrics."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        stats = feedback_dao.get_stats(30)
        
        # Get real community impact data from database
        community_metrics = {
            "total_contributors": 0,
            "total_feedback_submitted": stats.get("total_feedback", 0),
            "average_rating": stats.get("avg_rating", 0),
            "community_satisfaction": "high" if stats.get("avg_rating", 0) > 4 else "moderate" if stats.get("avg_rating", 0) > 2 else "low",
            "top_contributors": []
        }
        
        # Get real contributor data
        try:
            with feedback_dao.dao.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get unique contributors count
                    cur.execute("""
                        SELECT COUNT(DISTINCT user_session) 
                        FROM user_feedback 
                        WHERE user_session IS NOT NULL;
                    """)
                    
                    unique_contributors = cur.fetchone()[0] or 0
                    community_metrics["total_contributors"] = unique_contributors
                    
                    # Get top contributors (anonymized)
                    cur.execute("""
                        SELECT user_session, COUNT(*) as contribution_count
                        FROM user_feedback 
                        WHERE user_session IS NOT NULL
                        GROUP BY user_session 
                        ORDER BY contribution_count DESC 
                        LIMIT 5;
                    """)
                    
                    contributors = cur.fetchall()
                    
                    for i, (session, count) in enumerate(contributors):
                        community_metrics["top_contributors"].append({
                            "name": f"Contributor {i+1}",  # Anonymized
                            "contributions": count
                        })
                    
                    # If no contributors, show empty list instead of fake data
                    if not community_metrics["top_contributors"]:
                        community_metrics["top_contributors"] = []
                        
        except Exception as e:
            logger.error(f"Failed to get real contributor data: {e}")
            # Keep the basic stats but don't add fake contributors
        
        return community_metrics
        
    except Exception as e:
        logger.error(f"Failed to get community impact: {e}")
        return {"error": str(e)}



# Admin Feedback Management Endpoints

@app.get("/api/admin/feedback")
async def get_admin_feedback_list(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    rating_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """Get paginated feedback list for admin management."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        
        # Get real feedback data
        feedback_data = feedback_dao.get_feedback_list(limit=limit, offset=offset)
        
        return {
            "feedback": feedback_data['feedback'],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": feedback_data['total'],
                "has_more": feedback_data['has_more']
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get admin feedback list: {e}")
        return {"error": str(e)}

@app.get("/api/admin/feedback/{feedback_id}")
async def get_feedback_detail(feedback_id: int):
    """Get detailed feedback information for admin review."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        # Return simplified feedback detail
        return {"error": "Feedback detail not available in simplified system"}
        
    except Exception as e:
        logger.error(f"Failed to get feedback detail: {e}")
        return {"error": str(e)}

@app.put("/api/admin/feedback/{feedback_id}")
async def update_feedback_status(feedback_id: int, update_data: dict):
    """Update feedback status and admin notes."""
    try:
        # Simplified admin update - not available in clean system
        return {"error": "Admin feedback updates not available in simplified system"}
            
    except Exception as e:
        logger.error(f"Failed to update feedback: {e}")
        return {"error": str(e)}

@app.get("/api/admin/feedback/analytics")
async def get_feedback_analytics(days: int = Query(30, ge=1, le=365)):
    """Get comprehensive feedback analytics for admin dashboard."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        stats = feedback_dao.get_stats(days)
        
        # Create simplified analytics from available stats
        analytics = {
            "total_feedback": stats.get("total_feedback", 0),
            "average_rating": stats.get("avg_rating", 0),
            "positive_feedback": stats.get("positive_feedback", 0),
            "rating_distribution": stats.get("rating_distribution", {}),
            "trends": {
                "rating_trend": "stable",
                "volume_trend": "stable"
            }
        }
        
        return {
            "time_period_days": days,
            "analytics": analytics
        }
        
    except Exception as e:
        logger.error(f"Failed to get feedback analytics: {e}")
        return {"error": str(e)}

@app.get("/api/admin/feedback/export")
async def export_feedback_data(
    format: str = Query("csv", regex="^(csv|json)$"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None),
    rating_filter: Optional[str] = Query(None),
    accuracy_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    """Export feedback data in CSV or JSON format."""
    try:
        # Export not available in simplified system
        return {"error": "Export functionality not available in simplified system"}
        from fastapi.responses import StreamingResponse
        
        feedback_dao = get_feedback_dao()
        
        # Get feedback data with filters
        feedback_list = feedback_dao.get_admin_feedback_list(
            limit=limit,
            offset=offset,
            status=status,
            rating_filter=rating_filter,
            search=search
        )
        
        if format == "csv":
            # Create CSV response
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['ID', 'Query', 'Rating', 'Accurate', 'Helpful', 'Status', 'Created At'])
            
            # Write data
            for feedback in feedback_list:
                writer.writerow([
                    feedback['id'],
                    feedback['query_text'][:100] + '...' if len(feedback['query_text']) > 100 else feedback['query_text'],
                    feedback['rating'],
                    feedback['is_accurate'],
                    feedback['is_helpful'],
                    feedback['status'],
                    feedback['created_at']
                ])
            
            output.seek(0)
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=feedback_export.csv"}
            )
        else:
            # JSON format
            return {"feedback": feedback_list}
            
    except Exception as e:
        logger.error(f"Failed to export feedback data: {e}")
        return {"error": str(e)}



# Improvement Tracking API Endpoints

@app.post("/api/admin/improvements")
async def record_improvement(improvement_data: dict):
    """Record a new improvement action."""
    try:
        from .improvement_tracker import get_improvement_tracker, ImprovementAction, ImprovementType
        
        tracker = get_improvement_tracker()
        
        improvement = ImprovementAction(
            feedback_id=improvement_data.get('feedback_id'),
            action_type=ImprovementType(improvement_data.get('action_type', 'other')),
            description=improvement_data.get('description', ''),
            implemented_at=datetime.fromisoformat(improvement_data['implemented_at']) if improvement_data.get('implemented_at') else None,
            created_by=improvement_data.get('created_by', 'admin')
        )
        
        improvement_id = tracker.record_improvement(improvement)
        
        return {
            "success": True,
            "improvement_id": improvement_id,
            "message": "Improvement recorded successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to record improvement: {e}")
        return {"error": str(e)}

@app.get("/api/admin/improvements/summary")
async def get_improvement_summary(days: int = Query(30, ge=1, le=365)):
    """Get improvement summary and impact metrics."""
    try:
        from .improvement_tracker import get_improvement_tracker
        
        tracker = get_improvement_tracker()
        summary = tracker.get_improvement_summary(days=days)
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get improvement summary: {e}")
        return {"error": str(e)}

@app.get("/api/admin/improvements/recommendations")
async def get_improvement_recommendations():
    """Get automated improvement recommendations."""
    try:
        from .improvement_tracker import get_improvement_tracker
        
        tracker = get_improvement_tracker()
        recommendations = tracker.get_improvement_recommendations()
        
        return {"recommendations": recommendations}
        
    except Exception as e:
        logger.error(f"Failed to get improvement recommendations: {e}")
        return {"error": str(e)}

@app.post("/api/admin/improvements/{improvement_id}/measure")
async def measure_improvement_impact(improvement_id: int, measurement_days: int = Query(7, ge=3, le=30)):
    """Measure the impact of a specific improvement."""
    try:
        from .improvement_tracker import get_improvement_tracker
        
        tracker = get_improvement_tracker()
        impact_metrics = tracker.measure_improvement_impact(improvement_id, measurement_days)
        
        if impact_metrics:
            return {
                "success": True,
                "improvement_id": improvement_id,
                "impact_metrics": {
                    "before_avg_rating": impact_metrics.before_avg_rating,
                    "after_avg_rating": impact_metrics.after_avg_rating,
                    "rating_improvement": impact_metrics.after_avg_rating - impact_metrics.before_avg_rating,
                    "before_accuracy_rate": impact_metrics.before_accuracy_rate,
                    "after_accuracy_rate": impact_metrics.after_accuracy_rate,
                    "accuracy_improvement": impact_metrics.after_accuracy_rate - impact_metrics.before_accuracy_rate,
                    "before_helpfulness_rate": impact_metrics.before_helpfulness_rate,
                    "after_helpfulness_rate": impact_metrics.after_helpfulness_rate,
                    "helpfulness_improvement": impact_metrics.after_helpfulness_rate - impact_metrics.before_helpfulness_rate,
                    "feedback_count_before": impact_metrics.feedback_count_before,
                    "feedback_count_after": impact_metrics.feedback_count_after,
                    "measurement_period_days": impact_metrics.improvement_period_days,
                    "measurement_date": impact_metrics.measurement_date.isoformat() if impact_metrics.measurement_date else None
                }
            }
        else:
            return {"error": "Improvement not found or not yet implemented"}
            
    except Exception as e:
        logger.error(f"Failed to measure improvement impact: {e}")
        return {"error": str(e)}

@app.post("/api/admin/improvements/auto-measure")
async def auto_measure_improvements(days_back: int = Query(7, ge=1, le=30)):
    """Automatically measure impact for recent improvements."""
    try:
        from .improvement_tracker import get_improvement_tracker
        
        tracker = get_improvement_tracker()
        results = tracker.auto_measure_recent_improvements(days_back)
        
        return {
            "success": True,
            "measurements_attempted": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Failed to auto-measure improvements: {e}")
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


@app.post("/api/feedback/create-sample-improvements")
async def create_sample_improvements():
    """Create sample improvement actions for demonstration purposes."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        feedback_dao = get_clean_feedback_dao()
        
        # Get some recent feedback to create improvements for
        with feedback_dao.dao.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, query_text, missing_info, rating 
                    FROM user_feedback 
                    WHERE created_at >= %s 
                    ORDER BY created_at DESC 
                    LIMIT 5;
                """, (datetime.now() - timedelta(days=30),))
                
                recent_feedback = cur.fetchall()
        
        improvements_created = 0
        
        for feedback_id, query_text, missing_info, rating in recent_feedback:
            # Create different types of improvements based on feedback
            if missing_info:
                feedback_dao.create_improvement_action(
                    feedback_id=feedback_id,
                    action_type="document_update",
                    description=f"Added documentation to address missing information about: {missing_info[:100]}...",
                    created_by="admin"
                )
                improvements_created += 1
            
            if rating and rating <= 2:
                feedback_dao.create_improvement_action(
                    feedback_id=feedback_id,
                    action_type="source_boost",
                    description=f"Improved source ranking for queries similar to: {query_text[:100]}...",
                    created_by="system"
                )
                improvements_created += 1
        
        # Create some general improvements
        if improvements_created == 0:
            # Create sample improvements if no recent feedback
            sample_improvements = [
                {
                    "action_type": "prompt_update",
                    "description": "Updated response generation prompts to provide more accurate and helpful answers based on user feedback patterns."
                },
                {
                    "action_type": "source_boost",
                    "description": "Improved search algorithm to better prioritize high-quality sources based on user preferences."
                },
                {
                    "action_type": "document_update",
                    "description": "Added new documentation sections to address commonly requested information gaps."
                }
            ]
            
            for improvement in sample_improvements:
                with feedback_dao.dao.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO improvement_actions (
                                action_type, description, created_by
                            ) VALUES (%s, %s, %s);
                        """, (improvement["action_type"], improvement["description"], "system"))
                        conn.commit()
                        improvements_created += 1
        
        return {
            "success": True,
            "improvements_created": improvements_created,
            "message": f"Created {improvements_created} sample improvement actions"
        }
        
    except Exception as e:
        logger.error(f"Failed to create sample improvements: {e}")
        return {"error": str(e)}

@app.get("/api/feedback/personal-impact")
async def get_personal_feedback_impact(session_id: str):
    """Get personalized feedback impact metrics for a user session."""
    try:
        from .feedback_clean import get_clean_feedback_dao
        
        # Return simplified personal impact data
        return {
            "personal_stats": {
                "total_feedback": 0,
                "avg_rating": 0,
                "contributions": 0
            },
            "improvements_made": []
        }
        
        with feedback_dao.dao.get_connection() as conn:
            with conn.cursor() as cur:
                # Get user's feedback stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_feedback,
                        AVG(rating) as avg_rating,
                        COUNT(CASE WHEN is_accurate = true THEN 1 END) as accurate_feedback,
                        COUNT(CASE WHEN status = 'addressed' THEN 1 END) as addressed_feedback,
                        MIN(created_at) as first_feedback,
                        MAX(created_at) as latest_feedback
                    FROM user_feedback 
                    WHERE user_session = %s;
                """, (session_id,))
                
                user_stats = cur.fetchone()
                
                # Get improvements made based on user's feedback
                cur.execute("""
                    SELECT 
                        ia.action_type,
                        ia.description,
                        ia.implemented_at,
                        uf.query_text
                    FROM improvement_actions ia
                    JOIN user_feedback uf ON ia.feedback_id = uf.id
                    WHERE uf.user_session = %s
                    ORDER BY ia.implemented_at DESC
                    LIMIT 5;
                """, (session_id,))
                
                user_improvements = []
                for row in cur.fetchall():
                    action_type, description, implemented_at, query_text = row
                    user_improvements.append({
                        'action_type': action_type,
                        'description': description,
                        'implemented_at': implemented_at,
                        'original_query': query_text
                    })
                
                # Calculate user's contribution rank
                cur.execute("""
                    WITH user_ranks AS (
                        SELECT 
                            user_session,
                            COUNT(*) as feedback_count,
                            RANK() OVER (ORDER BY COUNT(*) DESC) as rank
                        FROM user_feedback 
                        WHERE user_session IS NOT NULL
                        AND created_at >= %s
                        GROUP BY user_session
                    )
                    SELECT rank, feedback_count
                    FROM user_ranks 
                    WHERE user_session = %s;
                """, (datetime.now() - timedelta(days=90), session_id))
                
                rank_result = cur.fetchone()
                user_rank = rank_result[0] if rank_result else None
                
                if user_stats:
                    total_feedback, avg_rating, accurate_feedback, addressed_feedback, first_feedback, latest_feedback = user_stats
                    
                    return {
                        "success": True,
                        "personal_stats": {
                            "total_feedback": total_feedback or 0,
                            "avg_rating": float(avg_rating) if avg_rating else 0.0,
                            "accurate_feedback": accurate_feedback or 0,
                            "addressed_feedback": addressed_feedback or 0,
                            "first_feedback": first_feedback.isoformat() if first_feedback else None,
                            "latest_feedback": latest_feedback.isoformat() if latest_feedback else None,
                            "contribution_rank": user_rank,
                            "accuracy_rate": (accurate_feedback / total_feedback * 100) if total_feedback > 0 else 0
                        },
                        "improvements_made": user_improvements,
                        "impact_summary": {
                            "improvements_triggered": len(user_improvements),
                            "feedback_addressed": addressed_feedback or 0,
                            "contribution_level": get_contribution_level(total_feedback or 0)
                        }
                    }
                else:
                    return {
                        "success": True,
                        "personal_stats": {
                            "total_feedback": 0,
                            "avg_rating": 0.0,
                            "accurate_feedback": 0,
                            "addressed_feedback": 0,
                            "first_feedback": None,
                            "latest_feedback": None,
                            "contribution_rank": None,
                            "accuracy_rate": 0
                        },
                        "improvements_made": [],
                        "impact_summary": {
                            "improvements_triggered": 0,
                            "feedback_addressed": 0,
                            "contribution_level": "New Contributor"
                        }
                    }
        
    except Exception as e:
        logger.error(f"Failed to get personal feedback impact: {e}")
        return {"error": str(e)}

def get_contribution_level(feedback_count: int) -> str:
    """Get contribution level based on feedback count."""
    if feedback_count >= 50:
        return "Expert Contributor"
    elif feedback_count >= 20:
        return "Active Contributor"
    elif feedback_count >= 10:
        return "Regular Contributor"
    elif feedback_count >= 5:
        return "Contributing Member"
    elif feedback_count >= 1:
        return "New Contributor"
    else:
        return "Visitor"





# File Cleanup and Sync Endpoints

@app.post("/api/admin/cleanup-orphaned")
async def cleanup_orphaned_endpoint():
    """Remove documents from database that no longer exist in the file system and invalidate related caches."""
    try:
        from .file_cleanup import cleanup_orphaned_documents
        from pathlib import Path
        
        settings = get_settings()
        base_path = Path(settings.auto_ingest_path) if settings.auto_ingest_path else Path(".")
        
        removed_count, removed_files, cache_invalidated = cleanup_orphaned_documents(base_path)
        
        return {
            "success": True,
            "documents_removed": removed_count,
            "files_cleaned": removed_files,
            "cache_entries_invalidated": cache_invalidated,
            "message": f"Removed {removed_count} orphaned documents from {len(removed_files)} files and invalidated {cache_invalidated} cache entries"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned documents: {e}")
        return {"error": str(e)}

@app.get("/api/admin/file-sync-status")
async def get_file_sync_status():
    """Get detailed status of database vs filesystem synchronization."""
    try:
        from .file_cleanup import get_database_file_status
        from pathlib import Path
        
        settings = get_settings()
        base_path = Path(settings.auto_ingest_path) if settings.auto_ingest_path else Path(".")
        
        status = get_database_file_status(base_path)
        
        return {
            "sync_status": status["sync_status"],
            "summary": {
                "total_db_documents": status["total_db_documents"],
                "database_files": len(status["database_files"]),
                "filesystem_files": len(status["filesystem_files"]),
                "orphaned_files": len(status["orphaned_in_database"]),
                "missing_files": len(status["missing_from_database"]),
                "synchronized_files": len(status["synchronized_files"])
            },
            "details": {
                "orphaned_in_database": status["orphaned_in_database"],
                "missing_from_database": status["missing_from_database"],
                "synchronized_files": status["synchronized_files"]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get file sync status: {e}")
        return {"error": str(e)}

@app.post("/api/admin/sync-database")
async def sync_database_with_filesystem():
    """Comprehensive sync of database with file system."""
    try:
        from .file_cleanup import sync_database_with_filesystem
        from pathlib import Path
        
        settings = get_settings()
        base_path = Path(settings.auto_ingest_path) if settings.auto_ingest_path else Path(".")
        
        result = sync_database_with_filesystem(base_path)
        
        return {
            "success": True,
            "sync_result": result,
            "message": f"Sync completed. Removed {result['orphaned_documents_removed']} orphaned documents."
        }
        
    except Exception as e:
        logger.error(f"Failed to sync database: {e}")
        return {"error": str(e)}

@app.post("/api/admin/invalidate-cache-by-source")
async def invalidate_cache_by_source(source_file: str):
    """Manually invalidate cache entries that reference a specific source file."""
    try:
        from .response_cache import get_response_cache
        from .query_result_cache import get_query_result_cache
        
        response_cache = get_response_cache()
        query_cache = get_query_result_cache()
        
        response_invalidated = response_cache.invalidate_by_source(source_file)
        query_invalidated = query_cache.invalidate_by_source(source_file)
        total_invalidated = response_invalidated + query_invalidated
        
        return {
            "success": True,
            "source_file": source_file,
            "response_cache_invalidated": response_invalidated,
            "query_cache_invalidated": query_invalidated,
            "total_invalidated": total_invalidated,
            "message": f"Invalidated {total_invalidated} cache entries referencing {source_file}"
        }
        
    except Exception as e:
        logger.error(f"Failed to invalidate cache by source: {e}")
        return {"error": str(e)}