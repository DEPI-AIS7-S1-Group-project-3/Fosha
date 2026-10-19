"""FastAPI app: Frontend -> this API -> Agent (agents/) -> RAG (rag/) -> data.

Run from the repository root:
    uv run uvicorn backend.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from backend import __version__
from backend.config import Settings, get_settings
from backend.errors import register_error_handlers
from backend.routers import attractions, chat, itinerary, system
from backend.services import retrieval
from backend.services.analytics import Analytics
from backend.services.cache import TTLCache
from backend.services.chat import ChatService
from backend.services.sessions import SessionStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("rehlaguide.api")


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        retrieval.enable_vector_store_cache()
        if settings.warmup_on_startup:
            await run_in_threadpool(retrieval.warmup)
        yield

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan,
                  description="Egypt travel assistant API (DEPI capstone).")

    cache = TTLCache(settings.cache_ttl_seconds, settings.cache_max_entries)
    analytics = Analytics()
    app.state.settings = settings
    app.state.cache = cache
    app.state.analytics = analytics
    app.state.chat_service = ChatService(cache, SessionStore(settings.session_ttl_seconds), analytics)

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_credentials="*" not in settings.cors_origins,
                       allow_methods=["*"], allow_headers=["*"],
                       expose_headers=["X-Request-ID", "X-Process-Time-Ms"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed:.1f}"
        logger.info("%s %s %s %.0fms [%s]", request.method, request.url.path,
                    response.status_code, elapsed, request_id)
        return response

    register_error_handlers(app)
    for module in (chat, itinerary, attractions, system):
        app.include_router(module.router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"name": settings.app_name, "version": __version__, "docs": "/docs",
                "api": settings.api_prefix}

    return app


app = create_app()
