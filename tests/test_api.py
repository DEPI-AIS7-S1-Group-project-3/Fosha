"""API + analytics, run against the offline demo pipeline (no Gemini, no Chroma)."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from api import analytics, server


@pytest.fixture
def client(tmp_path, monkeypatch):
    log = tmp_path / "analytics.jsonl"
    monkeypatch.setattr(analytics, "LOG_PATH", log)
    monkeypatch.setattr(server, "DEMO", True)
    monkeypatch.setattr(server, "cache", server.ResponseCache())
    return TestClient(server.app)


def test_chat_plans_and_enriches_stops(client):
    data = client.post("/api/v1/chat", json={"message": "2 days in Luxor, I love temples"}).json()
    assert data["ok"] and data["status"] == "planned"
    stop = data["itinerary"]["days"][0]["stops"][0]
    assert {"category", "lat", "lon", "price_foreigner_egp", "description"} <= stop.keys()
    assert data["cached"] is False


def test_repeat_message_is_served_from_cache(client):
    client.post("/api/v1/chat", json={"message": "2 days in Luxor"})
    again = client.post("/api/v1/chat", json={"message": "  2 DAYS in luxor "}).json()
    assert again["cached"] is True


def test_analytics_counts_language_destination_and_cache(client):
    client.post("/api/v1/chat", json={"message": "2 days in Luxor"})
    client.post("/api/v1/chat", json={"message": "2 days in Luxor"})
    client.post("/api/v1/chat", json={"message": "ثلاثة أيام في أسوان"})
    stats = client.get("/api/v1/analytics?days=7").json()
    assert stats["current"]["total_queries"] == 3
    assert stats["current"]["languages"] == {"en": 2, "ar": 1}
    assert stats["current"]["cache_hit_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert stats["destinations"][0] == {"name": "Luxor", "count": 2}
    assert stats["attractions"] and stats["regions"]


def test_empty_message_is_rejected(client):
    assert client.post("/api/v1/chat", json={"message": ""}).status_code == 422


def test_pages_are_served(client):
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert "root" in res_home.text or "globe.js" in res_home.text

    res_dash = client.get("/dashboard")
    assert res_dash.status_code == 200
    assert "root" in res_dash.text or "dashboard.js" in res_dash.text

