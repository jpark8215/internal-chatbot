from fastapi import FastAPI, HTTPException
import logging
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
import threading
from pathlib import Path as _Path

app = FastAPI(title="Internal Chatbot API")
settings = get_settings()
_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.on_event("startup")
async def _maybe_auto_ingest():
    settings_local = get_settings()
    # Only if DB is configured and auto-ingest is enabled
    if not (settings_local.auto_ingest_on_start and (settings_local.database_url or settings_local.db_host)):
        return
    target = settings_local.auto_ingest_path
    if not target or not _Path(target).exists():
        return
    try:
        dao = get_dao()
        if dao.count_documents() > 0:
            return
    except Exception:
        return

    def _run():
        try:
            total = ingest_path(_Path(target))
            logging.info(f"[auto-ingest] Ingested {total} chunks from {target}")
        except Exception as e:
            logging.error(f"[auto-ingest] Failed: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

@app.on_event("shutdown")
async def _shutdown():
    llm = get_local_llm()
    try:
        await llm.close()
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


@app.get("/")
async def root():
    """Serve chat UI if present; otherwise show basic API info."""
    index_path = _static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "message": "Internal chatbot API",
        "docs": "/docs",
        "health": "/health"
    }


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
                "streaming": False  # Future feature
            }
        }
    except Exception as e:
        return {
            "app": "internal-chatbot",
            "error": str(e),
            "features": {
                "chat": False,
                "streaming": False
            }
        }


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate text using the local LLM."""
    llm = get_local_llm()
    
    try:
        # Try retrieval augmentation if DB configured
        settings_local = get_settings()
        system_parts = []
        if settings_local.database_url or settings_local.db_host:
            try:
                vectors = await embed_texts([req.prompt])
                query_vec = vectors[0]
                dao = get_dao()
                matches = dao.search(query_vec, top_k=5)
                if matches:
                    ctx_chunks = "\n\n".join(
                        [f"[Source {i+1}]\n{content}" for i, (_id, content, _dist) in enumerate(matches)]
                    )
                    system_parts.append(
                        "You are a policy assistant. Answer strictly based on the provided policy context.\n"
                        "If the context does not contain the answer, say you don't know.\n"
                        "Cite sources as [Source N].\n\nPolicy context:\n" + ctx_chunks
                    )
            except Exception as e:
                # Retrieval is optional; continue without augmentation on failure
                print(f"[retrieve] Skipping retrieval due to error: {e}")

        if req.system_prompt:
            system_parts.insert(0, req.system_prompt)
        composed_system = "\n\n".join(system_parts) if system_parts else req.system_prompt

        # Build request (possibly augmented)
        augmented_req = GenerateRequest(
            prompt=req.prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            system_prompt=composed_system,
        )

        result = await llm.generate(augmented_req)
        return GenerateResponse(
            ok=True,
            text=result["text"],
            model=result["model"]
        )
        
    except ModelNotFoundError as e:
        return GenerateResponse(
            ok=False,
            reason=str(e)
        )
        
    except GenerationError as e:
        return GenerateResponse(
            ok=False,
            reason=f"Generation failed: {str(e)}"
        )
        
    except Exception as e:
        return GenerateResponse(
            ok=False,
            reason=f"Unexpected error: {str(e)}"
        )
