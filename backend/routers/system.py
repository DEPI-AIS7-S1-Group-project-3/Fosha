import os

from fastapi import APIRouter, Depends

from agents.attractions import load_attractions
from backend import __version__
from backend.dependencies import get_analytics, get_cache
from backend.schemas import AnalyticsResponse, HealthResponse
from backend.services import retrieval
from backend.services.analytics import Analytics
from backend.services.cache import TTLCache

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Readiness: /chat needs the vector index and a Gemini key; /attractions needs neither."""
    checks = {
        "attractions_loaded": len(load_attractions()),
        "vector_index_present": retrieval.index_exists(),
        "vector_store_loaded": retrieval.vector_store_loaded(),
        "llm_configured": bool(os.environ.get("GEMINI_API_KEY")),
    }
    ready = checks["attractions_loaded"] > 0 and checks["vector_index_present"] and checks["llm_configured"]
    return {"status": "ok" if ready else "degraded", "version": __version__, "checks": checks}


@router.get("/analytics", response_model=AnalyticsResponse)
def analytics(stats: Analytics = Depends(get_analytics), cache: TTLCache = Depends(get_cache)) -> dict:
    """Usage counters for the dashboard. Reset on server restart."""
    return stats.snapshot(cache.stats())


@router.delete("/cache", status_code=204)
def clear_cache(cache: TTLCache = Depends(get_cache)) -> None:
    """Drop cached answers, e.g. after the data pipeline updates attractions."""
    cache.clear()
