"""Request/response models = the API contract with the frontend (Member 4).
Shapes coming from the agent (intent, itinerary) are passed through as plain dicts,
so changes inside agents/ do not break validation here.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

Status = Literal["planned", "needs_clarification", "unsupported_region", "out_of_scope", "no_results"]


# ---------- chat ----------

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, examples=["2 days in Cairo, I love museums"])
    session_id: Optional[str] = Field(None, max_length=64,
                                      description="Returned by the first /chat call; send it back to continue the conversation.")


class ChatResponse(BaseModel):
    session_id: str
    status: Status
    language: Literal["ar", "en"]
    reply: str
    intent: Dict[str, Any]
    itinerary: Optional[Dict[str, Any]] = None
    missing: Optional[List[str]] = None
    used_fallback: Optional[bool] = None
    cached: bool = False


# ---------- itinerary (deterministic, no LLM) ----------

class ItineraryRequest(BaseModel):
    attraction_ids: List[int] = Field(..., min_length=1, max_length=40, description="Most relevant first.")
    days: int = Field(..., ge=1, le=14)
    first_day: Optional[str] = Field(None, description="Weekday name or YYYY-MM-DD of day 1.")
    day_start: str = Field("09:00", pattern=r"^\d{2}:\d{2}$")
    day_end: str = Field("18:00", pattern=r"^\d{2}:\d{2}$")
    max_stops_per_day: int = Field(4, ge=1, le=8)
    visitor_type: Optional[Literal["egyptian", "foreigner"]] = None


class ItineraryResponse(BaseModel):
    days: List[Dict[str, Any]]
    unscheduled: List[Dict[str, Any]]
    warnings: List[str]


# ---------- attractions ----------

class Location(BaseModel):
    lat: float
    lon: float
    note: str = ""


class OpeningHours(BaseModel):
    text: str
    default: List[List[str]] = []
    overrides: Dict[str, List[List[str]]] = {}
    confidence: str = "unknown"
    note: str = ""


class DataFreshness(BaseModel):
    last_verified: str
    source_url: str
    days_since_verified: Optional[int] = None
    stale: bool = False
    warnings: List[str] = []


class AttractionSummary(BaseModel):
    id: int
    name: str
    city: str
    region: str
    category: str
    duration_min: int
    price_egyptian_egp: float
    price_foreigner_egp: float
    location: Optional[Location] = None


class AttractionDetail(AttractionSummary):
    description: str
    opening_hours: OpeningHours
    freshness: DataFreshness


class AttractionList(BaseModel):
    total: int
    items: List[AttractionSummary]


class OpeningCheck(BaseModel):
    attraction_id: int
    day: str
    start: str
    open: Optional[bool]
    reason: Optional[str] = None
    windows: List[Any] = []
    confidence: str
    note: str = ""


# ---------- analytics / health ----------

class CountItem(BaseModel):
    name: str
    count: int


class CacheStats(BaseModel):
    hits: int
    misses: int
    hit_rate: float
    entries: int


class AnalyticsResponse(BaseModel):
    total_queries: int
    errors: int
    avg_response_ms: float
    uptime_seconds: int
    statuses: Dict[str, int]
    languages: Dict[str, int]
    top_regions: List[CountItem]
    top_attractions: List[CountItem]
    top_interests: List[CountItem]
    cache: CacheStats


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    checks: Dict[str, Any]
