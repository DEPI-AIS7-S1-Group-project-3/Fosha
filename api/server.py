"""HTTP API for the Fosha web UI (frontend/), and the static UI itself.

    uv run uvicorn api.server:app --reload            # real Gemini + Chroma
    REHLA_DEMO=1 uv run uvicorn api.server:app        # offline demo, no key needed
    REHLA_SEARCH=keyword uv run uvicorn api.server:app  # real Gemini, keyword search instead of Chroma

Endpoints:
    POST /api/v1/chat       {"message": str}  -> plan_trip() result + UI extras
    GET  /api/v1/analytics  ?days=7|30|0      -> dashboard aggregates (0 = all time)
    GET  /api/v1/health                        -> {"ok": true, "demo": bool}
    GET  /                                     -> traveller app (frontend/index.html)
    GET  /dashboard                            -> insights dashboard (frontend/dashboard.html)
"""
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.attractions import get_attraction
from agents.places_online import arabic_area, arabic_name, is_dynamic
from agents.planner import plan_trip
from agents.travel import load_locations
from api import analytics

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
DEMO = os.environ.get("REHLA_DEMO", "").lower() in ("1", "true", "yes")
# Real Gemini with the demo keyword search: for machines without a Chroma index
# (e.g. Intel Macs, where sentence-transformers can't be installed).
KEYWORD_SEARCH = os.environ.get("REHLA_SEARCH", "").lower() == "keyword"
CACHE_SIZE = 256
# Only answers that do not depend on a model hiccup are worth repeating.
CACHEABLE = {"planned", "needs_clarification", "unsupported_region", "out_of_scope", "no_results"}

app = FastAPI(title="Fosha API (RehlaGuide)", version="0.2.0")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ResponseCache:
    """Small LRU keyed on the normalised message text."""

    def __init__(self, size: int = CACHE_SIZE):
        self.size = size
        self._items: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def key(message: str) -> str:
        return " ".join(message.lower().split())

    def get(self, message: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            k = self.key(message)
            if k in self._items:
                self._items.move_to_end(k)
                return self._items[k]
        return None

    def put(self, message: str, value: Dict[str, Any]) -> None:
        with self._lock:
            self._items[self.key(message)] = value
            self._items.move_to_end(self.key(message))
            while len(self._items) > self.size:
                self._items.popitem(last=False)


cache = ResponseCache()


def _enrich(itinerary: Dict[str, Any]) -> Dict[str, Any]:
    """Add what the UI needs to draw stop cards and the route map."""
    locations = load_locations()
    for day in itinerary.get("days", []):
        day["area_ar"] = arabic_area(day["area"])
        for stop in day["stops"]:
            a = get_attraction(stop["attraction_id"])
            loc = locations.get(stop["attraction_id"], {})
            stop.update({
                "category": a.category, "region": a.region, "city": a.city,
                "description": a.description,
                "price_foreigner_egp": a.price_foreigner_egp,
                "price_egyptian_egp": a.price_egyptian_egp,
                "source_url": a.source_url, "last_verified": a.last_verified,
                "lat": loc.get("lat"), "lon": loc.get("lon"),
                "name_ar": arabic_name(stop["attraction_id"]),
                "from_web": is_dynamic(stop["attraction_id"]),
            })
    if not itinerary.get("recommendations") and len(itinerary.get("days", [])) >= 2:
        from agents.recommendations import get_recommendations
        itinerary["recommendations"] = get_recommendations(None, len(itinerary["days"]), itinerary=itinerary)
    return itinerary


def _run_pipeline(message: str) -> Dict[str, Any]:
    if DEMO:
        from api.demo import demo_llm, demo_search
        return plan_trip(message, llm=demo_llm, search_fn=demo_search)
    if KEYWORD_SEARCH:
        from api.demo import demo_search
        return plan_trip(message, search_fn=demo_search)
    return plan_trip(message)


@app.get("/api/v1/health")
def health() -> Dict[str, Any]:
    return {"ok": True, "demo": DEMO, "search": "keyword" if DEMO or KEYWORD_SEARCH else "vector"}


@app.post("/api/v1/chat")
def chat(request: ChatRequest) -> Dict[str, Any]:
    started = time.perf_counter()
    result = cache.get(request.message)
    cached = result is not None
    if result is None:
        try:
            result = _run_pipeline(request.message)
        except Exception as exc:  # plan_trip should not raise; this is a last line of defence
            result = {"ok": False, "error": f"Unexpected error: {exc}"}
        if result.get("ok") and result.get("itinerary"):
            _enrich(result["itinerary"])
        if result.get("ok") and result.get("status") in CACHEABLE:
            cache.put(request.message, result)
    response_ms = round((time.perf_counter() - started) * 1000)
    analytics.record_event(result, cached=cached, response_ms=response_ms)
    return {**result, "cached": cached, "response_ms": response_ms, "demo": DEMO}


@app.get("/api/v1/analytics")
def get_analytics(days: int = 7) -> Dict[str, Any]:
    return analytics.summary(days=days or None)


DIST_DIR = FRONTEND_DIR / "dist"
if DIST_DIR.exists() and (DIST_DIR / "index.html").exists():
    if (DIST_DIR / "assets").exists():
        app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    @app.get("/dashboard")
    def serve_react_app() -> FileResponse:
        return FileResponse(DIST_DIR / "index.html")
elif FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/dashboard")
    def dashboard() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "dashboard.html")
