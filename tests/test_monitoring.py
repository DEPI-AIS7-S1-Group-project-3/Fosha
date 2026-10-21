"""Monitoring: per-request telemetry, health fields in the analytics log and the dashboard stats."""
import logging
import os
from unittest import mock

import pytest

from agents import llm, telemetry
from agents.retrieval_adapter import search_attractions
from api import analytics

LLM_ENV = {"LLM_PROVIDERS": "gemini", "GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "model-a",
           "GEMINI_FALLBACK_MODELS": "model-b"}


def run_llm(side_effect):
    with mock.patch.dict(os.environ, LLM_ENV), \
            mock.patch("agents.llm._call_gemini", side_effect=side_effect), \
            mock.patch("agents.llm.time.sleep"):
        return llm.generate("hi")


# --------------------------------------------------------------- telemetry --
def test_recording_outside_a_request_is_a_noop():
    telemetry.record_llm("m", ok=True, ms=5)
    telemetry.record_retrieval(0.5, 3)  # must not raise


def test_summary_of_an_empty_request():
    with telemetry.request() as m:
        pass
    s = m.summary()
    assert s["llm_calls"] == 0 and s["top1_distance"] is None and s["retrieval_empty"] is False


def test_requests_do_not_leak_into_each_other():
    with telemetry.request() as first:
        telemetry.record_llm("a", ok=True, ms=10)
    with telemetry.request() as second:
        pass
    assert first.summary()["llm_calls"] == 1 and second.summary()["llm_calls"] == 0


def test_llm_call_reports_model_latency_and_fallbacks():
    with telemetry.request() as m:
        result = run_llm([RuntimeError("503 UNAVAILABLE high demand"), "hello"])
    assert result["ok"] and "_skipped" not in result  # the public contract is unchanged
    s = m.summary()
    assert s["llm_calls"] == 1 and s["llm_failed"] == 0
    assert s["llm_fallbacks"] == 1 and s["llm_models"] == ["gemini/model-b"]


def test_failed_llm_call_is_counted_and_logged(caplog):
    caplog.set_level(logging.WARNING, logger="fosha")
    logging.getLogger("fosha").propagate = True  # configure_logging() turns it off for the app
    try:
        with telemetry.request() as m:
            result = run_llm(RuntimeError("404 NOT_FOUND model retired"))
    finally:
        logging.getLogger("fosha").propagate = False
    assert result["ok"] is False
    assert m.summary()["llm_failed"] == 1
    assert "llm call failed" in caplog.text


def test_retrieval_records_best_distance_even_when_cut_off():
    def fake(query, region=None, category=None, max_duration=None, top_k=5):
        return [{"content": "", "metadata": {"id": 5}, "relevance_score": 1.9},
                {"content": "", "metadata": {"id": 6}, "relevance_score": 2.1}]

    with telemetry.request() as m:
        r = search_attractions("something far away", search_fn=fake)
    assert r["results"] == [] and r["dropped_too_far"] == 2
    s = m.summary()
    assert s["top1_distance"] == 1.9 and s["retrieval_empty"] is True


# --------------------------------------------------------------- analytics --
def event(**over):
    base = {"ts": 1000.0, "ok": True, "status": "planned", "language": "en", "destination": "Luxor",
            "days": 2, "attraction_ids": [], "stops": [], "cached": False, "response_ms": 100}
    return {**base, **over}


def test_record_event_stores_health_fields(tmp_path):
    path = tmp_path / "a.jsonl"
    metrics = {"llm_calls": 2, "llm_failed": 1, "llm_fallbacks": 1, "llm_ms": 800,
               "llm_models": ["groq/x"], "top1_distance": 0.91, "retrieval_empty": False}
    e = analytics.record_event({"ok": False, "error": "boom " * 100}, cached=False,
                               response_ms=900, path=path, metrics=metrics)
    assert e["llm_failed"] == 1 and e["top1_distance"] == 0.91
    assert len(e["error"]) == 200  # long errors are truncated
    assert analytics.load_events(path)[0]["llm_models"] == ["groq/x"]


def test_record_event_without_metrics_uses_safe_defaults(tmp_path):
    e = analytics.record_event({"ok": True, "status": "planned"}, cached=True, response_ms=3,
                               path=tmp_path / "a.jsonl")
    assert e["llm_calls"] == 0 and e["error"] is None and e["top1_distance"] is None


def test_window_stats_health_rates():
    events = [
        event(response_ms=100, llm_calls=1, top1_distance=0.8),
        event(response_ms=200, llm_calls=2, llm_fallbacks=1, top1_distance=1.0),
        event(response_ms=900, llm_calls=1, llm_failed=1, ok=False, retrieval_empty=True),
        event(response_ms=5, cached=True),  # served from cache: no LLM, ignored for latency
    ]
    s = analytics._window_stats(events)
    assert s["error_rate"] == 0.25
    assert s["llm_failure_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["llm_fallback_rate"] == pytest.approx(1 / 3, abs=1e-3)
    assert s["empty_retrieval_rate"] == 0.25
    assert s["avg_top1_distance"] == 0.9
    assert s["p95_response_ms"] == 900


def test_window_stats_old_events_without_health_fields_count_as_healthy():
    s = analytics._window_stats([event(), event()])
    assert s["error_rate"] == 0.0 and s["llm_failure_rate"] == 0.0
    assert s["avg_top1_distance"] is None and s["p95_response_ms"] == 100


def test_window_stats_of_no_events_does_not_divide_by_zero():
    s = analytics._window_stats([])
    assert s["error_rate"] == 0.0 and s["p95_response_ms"] == 0
