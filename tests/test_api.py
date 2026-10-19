"""API tests. The agent is replaced by a fake plan function: no Gemini, no Chroma."""
import threading
import time

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.services.analytics import Analytics
from backend.services.cache import TTLCache, make_key, normalize_query
from backend.services.chat import ChatService
from backend.services.sessions import SessionStore

PLANNED = {
    "ok": True, "status": "planned", "language": "en", "reply": "Day 1 - Greater Cairo ...",
    "intent": {"task": "plan_trip", "region": "Cairo", "days": 1, "interests": ["museums"],
               "unsupported_region": None, "missing": []},
    "itinerary": {"ok": True, "days": [{"day": 1, "weekday": None, "area": "Greater Cairo",
                                        "stops": [{"attraction_id": 1, "name": "The Egyptian Museum",
                                                   "start": "09:00", "end": "11:00"}],
                                        "warnings": [], "notes": []}],
                  "unscheduled": [], "warnings": []},
    "used_fallback": False,
}
CLARIFY = {
    "ok": True, "status": "needs_clarification", "language": "en", "reply": "How many days?",
    "intent": {"task": "plan_trip", "region": "Cairo", "days": None, "interests": [], "missing": ["days"]},
    "missing": ["days"],
}


class FakePlanner:
    def __init__(self, responses):
        self.responses = responses  # message -> result, or a callable
        self.calls = []

    def __call__(self, message):
        self.calls.append(message)
        return self.responses(message) if callable(self.responses) else self.responses


def make_client(plan_fn, timeout_seconds=5):
    app = create_app(Settings(warmup_on_startup=False))
    state = app.state
    state.chat_service = ChatService(state.cache, SessionStore(), state.analytics, plan_fn=plan_fn,
                                     timeout_seconds=timeout_seconds)
    return TestClient(app)


# ---------- chat ----------

def test_chat_planned_returns_itinerary_and_session():
    client = make_client(FakePlanner(PLANNED))
    r = client.post("/api/v1/chat", json={"message": "1 day in Cairo, museums"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "planned"
    assert body["itinerary"]["days"][0]["stops"][0]["name"] == "The Egyptian Museum"
    assert body["session_id"] and body["cached"] is False


def test_chat_adds_ticket_prices_when_visitor_type_known():
    planned = {**PLANNED, "intent": {**PLANNED["intent"], "visitor_type": "foreigner"}}
    client = make_client(FakePlanner(planned))
    stop = client.post("/api/v1/chat", json={"message": "x"}).json()["itinerary"]["days"][0]["stops"][0]
    assert stop["ticket_price_egp"] == 550


def test_repeated_query_is_served_from_cache():
    planner = FakePlanner(PLANNED)
    client = make_client(planner)
    client.post("/api/v1/chat", json={"message": "1 day in Cairo, museums"})
    r = client.post("/api/v1/chat", json={"message": "  1 Day in CAIRO, museums!! "})
    assert r.json()["cached"] is True
    assert len(planner.calls) == 1
    stats = client.get("/api/v1/analytics").json()
    assert stats["cache"]["hits"] == 1 and stats["cache"]["hit_rate"] == 0.5
    assert stats["total_queries"] == 2


def test_clarification_answer_is_combined_with_original_request():
    planner = FakePlanner(lambda m: PLANNED if "3 days" in m else CLARIFY)
    client = make_client(planner)
    first = client.post("/api/v1/chat", json={"message": "Trip to Cairo"}).json()
    assert first["status"] == "needs_clarification" and first["missing"] == ["days"]

    second = client.post("/api/v1/chat", json={"message": "3 days", "session_id": first["session_id"]}).json()
    assert planner.calls[-1] == "Trip to Cairo\n3 days"
    assert second["status"] == "planned"

    history = client.get(f"/api/v1/sessions/{first['session_id']}").json()
    assert len(history["history"]) == 4 and history["awaiting_clarification"] is False


@pytest.mark.parametrize("error,status,code", [
    ("GEMINI_API_KEY is not set (put it in your .env file)", 503, "llm_not_configured"),
    ("Gemini call failed: 503 UNAVAILABLE", 502, "llm_unavailable"),
    ("Retrieval failed: no such table", 503, "retrieval_unavailable"),
    ("something odd", 502, "agent_error"),
])
def test_agent_errors_map_to_http_errors(error, status, code):
    planner = FakePlanner({"ok": False, "error": error})
    client = make_client(planner)
    r = client.post("/api/v1/chat", json={"message": "hi"})
    assert r.status_code == status
    assert r.json()["error"]["code"] == code
    # errors are not cached
    client.post("/api/v1/chat", json={"message": "hi"})
    assert len(planner.calls) == 2
    assert client.get("/api/v1/analytics").json()["errors"] == 2


def test_slow_agent_returns_504_and_late_answer_is_cached():
    release = threading.Event()

    def slow_planner(message):
        release.wait(5)
        return PLANNED

    client = make_client(slow_planner, timeout_seconds=0.2)
    r = client.post("/api/v1/chat", json={"message": "slow one"})
    assert r.status_code == 504 and r.json()["error"]["code"] == "llm_timeout"
    assert client.get("/api/v1/analytics").json()["errors"] == 1

    release.set()  # the model finally answers in the background...
    for _ in range(50):
        if client.app.state.cache.stats()["entries"]:
            break
        time.sleep(0.02)
    retry = client.post("/api/v1/chat", json={"message": "slow one"}).json()
    assert retry["cached"] is True and retry["status"] == "planned"  # ...so the retry is instant


def test_chat_validation_error_format():
    client = make_client(FakePlanner(PLANNED))
    r = client.post("/api/v1/chat", json={"message": ""})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
    assert r.json()["error"]["details"][0]["field"] == "message"


def test_analytics_counts_regions_languages_and_attractions():
    client = make_client(FakePlanner(PLANNED))
    client.post("/api/v1/chat", json={"message": "a"})
    client.post("/api/v1/chat", json={"message": "b"})
    stats = client.get("/api/v1/analytics").json()
    assert stats["languages"] == {"en": 2}
    assert stats["statuses"] == {"planned": 2}
    assert stats["top_regions"] == [{"name": "Cairo", "count": 2}]
    assert stats["top_attractions"][0] == {"name": "The Egyptian Museum", "count": 2}
    assert stats["top_interests"][0]["name"] == "museums"


def test_unknown_session_is_404():
    client = make_client(FakePlanner(PLANNED))
    assert client.get("/api/v1/sessions/nope").status_code == 404
    assert client.delete("/api/v1/sessions/nope").status_code == 404


# ---------- attractions ----------

def test_list_attractions_and_filters():
    client = make_client(FakePlanner(PLANNED))
    everything = client.get("/api/v1/attractions").json()
    assert everything["total"] == 30
    assert everything["items"][0]["location"]["lat"]

    cairo = client.get("/api/v1/attractions", params={"region": "cairo"}).json()
    assert {a["region"] for a in cairo["items"]} == {"Cairo", "Giza"}  # Greater Cairo

    museums = client.get("/api/v1/attractions", params={"category": "museum"}).json()
    assert museums["total"] > 0 and all(a["category"] == "Museum" for a in museums["items"])


def test_list_attractions_rejects_unknown_region():
    client = make_client(FakePlanner(PLANNED))
    r = client.get("/api/v1/attractions", params={"region": "Dahab"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_request"


def test_attraction_detail_has_hours_and_freshness():
    client = make_client(FakePlanner(PLANNED))
    body = client.get("/api/v1/attractions/1").json()
    assert body["name"] == "The Egyptian Museum"
    assert body["opening_hours"]["default"] == [["09:00", "17:00"]]
    assert body["freshness"]["last_verified"] and "stale" in body["freshness"]


def test_attraction_detail_flags_uncertain_hours():
    client = make_client(FakePlanner(PLANNED))
    body = client.get("/api/v1/attractions/5").json()  # id 5 has 'uncertain' hours
    assert any("not fully confirmed" in w for w in body["freshness"]["warnings"])


def test_attraction_not_found():
    client = make_client(FakePlanner(PLANNED))
    r = client.get("/api/v1/attractions/999")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_opening_check():
    client = make_client(FakePlanner(PLANNED))
    ok = client.get("/api/v1/attractions/1/opening", params={"day": "Monday", "start": "10:00"}).json()
    assert ok["open"] is True
    late = client.get("/api/v1/attractions/1/opening", params={"day": "Monday", "start": "16:30"}).json()
    assert late["open"] is False
    bad = client.get("/api/v1/attractions/1/opening", params={"day": "someday"})
    assert bad.status_code == 400


def test_regions_and_categories():
    client = make_client(FakePlanner(PLANNED))
    assert "Luxor" in client.get("/api/v1/regions").json()
    assert "Museum" in client.get("/api/v1/categories").json()


# ---------- itinerary ----------

def test_itinerary_from_ids_with_prices():
    client = make_client(FakePlanner(PLANNED))
    r = client.post("/api/v1/itinerary", json={"attraction_ids": [1, 4], "days": 1, "visitor_type": "foreigner"})
    assert r.status_code == 200
    stops = r.json()["days"][0]["stops"]
    assert stops and all("ticket_price_egp" in s for s in stops)


def test_itinerary_unknown_id_is_400():
    client = make_client(FakePlanner(PLANNED))
    r = client.post("/api/v1/itinerary", json={"attraction_ids": [999], "days": 1})
    assert r.status_code == 400


def test_itinerary_validation():
    client = make_client(FakePlanner(PLANNED))
    assert client.post("/api/v1/itinerary", json={"attraction_ids": [1], "days": 20}).status_code == 422


# ---------- system ----------

def test_health_reports_checks():
    client = make_client(FakePlanner(PLANNED))
    body = client.get("/api/v1/health").json()
    assert body["checks"]["attractions_loaded"] == 30
    assert body["status"] in ("ok", "degraded")


def test_clear_cache():
    planner = FakePlanner(PLANNED)
    client = make_client(planner)
    client.post("/api/v1/chat", json={"message": "x"})
    assert client.delete("/api/v1/cache").status_code == 204
    client.post("/api/v1/chat", json={"message": "x"})
    assert len(planner.calls) == 2


def test_response_headers():
    client = make_client(FakePlanner(PLANNED))
    r = client.get("/api/v1/regions", headers={"X-Request-ID": "abc"})
    assert r.headers["X-Request-ID"] == "abc" and "X-Process-Time-Ms" in r.headers


# ---------- cache / sessions units ----------

def test_cache_expiry_and_lru():
    now = [0.0]
    cache = TTLCache(ttl_seconds=10, max_entries=2, clock=lambda: now[0])
    cache.set("a", 1)
    cache.set("b", 2)
    cache.get("a")          # a is now most recent
    cache.set("c", 3)       # evicts b
    assert cache.get("b") is None and cache.get("a") == 1
    now[0] = 11
    assert cache.get("a") is None


def test_normalize_query_handles_arabic_digits_and_punctuation():
    assert normalize_query("  ٣ أيام في الأقصر!! ") == "3 أيام في الأقصر"
    assert make_key("2 Days, Cairo") == make_key("2 days cairo")


def test_sessions_expire():
    now = [0.0]
    store = SessionStore(ttl_seconds=10, clock=lambda: now[0])
    session = store.get_or_create(None)
    now[0] = 11
    assert store.get(session.id) is None


def test_analytics_empty_snapshot():
    snap = Analytics().snapshot(TTLCache().stats())
    assert snap["total_queries"] == 0 and snap["avg_response_ms"] == 0.0
