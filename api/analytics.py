"""Query log + aggregates for the Fosha insights dashboard (/dashboard).

Every /api/v1/chat call appends one JSON line to data/analytics.jsonl (gitignored).
The dashboard reads the same file, so numbers survive a server restart.
The raw message text is NOT stored, only what the dashboard needs.
"""
import json
import math
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from agents.attractions import get_attraction

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "analytics.jsonl"
_lock = threading.Lock()


def record_event(result: Dict[str, Any], cached: bool, response_ms: int,
                 path: Optional[Path] = None,
                 metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`metrics` is agents.telemetry.RequestMetrics.summary() for this request (LLM and
    retrieval health); it is empty for cached answers because nothing ran."""
    metrics = metrics or {}
    path = path or LOG_PATH
    intent = result.get("intent") or {}
    itinerary = result.get("itinerary") or {}
    event = {
        "ts": time.time(),
        "ok": bool(result.get("ok")),
        "status": result.get("status", "error"),
        "language": result.get("language") or intent.get("language") or "en",
        "destination": intent.get("region") or intent.get("unsupported_region"),
        "days": intent.get("days"),
        "attraction_ids": [s["attraction_id"] for d in itinerary.get("days", []) for s in d["stops"]],
        # Names stored too: places found online only exist in memory, so look-ups after a
        # restart would lose them.
        "stops": [{"id": s["attraction_id"], "name": s["name"], "name_ar": s.get("name_ar"),
                   "region": s.get("region"), "category": s.get("category")}
                  for d in itinerary.get("days", []) for s in d["stops"]],
        "cached": cached,
        "response_ms": response_ms,
        # health of this request (no message text): see agents/telemetry.py
        "error": None if result.get("ok") else str(result.get("error", ""))[:200],
        "llm_calls": metrics.get("llm_calls", 0),
        "llm_failed": metrics.get("llm_failed", 0),
        "llm_fallbacks": metrics.get("llm_fallbacks", 0),
        "llm_ms": metrics.get("llm_ms", 0),
        "llm_models": metrics.get("llm_models", []),
        "top1_distance": metrics.get("top1_distance"),
        "retrieval_empty": metrics.get("retrieval_empty", False),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    return event


def load_events(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    path = path or LOG_PATH
    if not path.exists():
        return []
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a half-written line must not break the dashboard
    return events


def _top(counter: Counter, n: int) -> List[Dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(n)]


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def _percentile(values: List[float], q: float) -> int:
    """Nearest-rank percentile (q in 0..1); 0 for no data."""
    if not values:
        return 0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(q * len(ordered)) - 1)])


def _window_stats(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    events = list(events)
    total = len(events)
    with_llm = [e for e in events if e.get("llm_calls")]
    distances = [e["top1_distance"] for e in events if e.get("top1_distance") is not None]
    languages = Counter(e["language"] for e in events)
    cached = sum(1 for e in events if e.get("cached"))
    fresh_times = [e["response_ms"] for e in events if not e.get("cached")]
    return {
        "total_queries": total,
        "cache_hit_rate": round(cached / total, 4) if total else 0.0,
        "avg_response_ms": round(sum(fresh_times) / len(fresh_times)) if fresh_times else 0,
        "languages": {"en": languages.get("en", 0), "ar": languages.get("ar", 0)},
        "planned": sum(1 for e in events if e.get("status") == "planned"),
        # --- health (events logged before these fields existed count as healthy) ---
        "error_rate": _rate(sum(1 for e in events if not e.get("ok")), total),
        "p95_response_ms": _percentile(fresh_times, 0.95),
        "llm_failure_rate": _rate(sum(1 for e in with_llm if e.get("llm_failed")), len(with_llm)),
        "llm_fallback_rate": _rate(sum(1 for e in with_llm if e.get("llm_fallbacks")), len(with_llm)),
        "empty_retrieval_rate": _rate(sum(1 for e in events if e.get("retrieval_empty")), total),
        "avg_top1_distance": round(sum(distances) / len(distances), 4) if distances else None,
    }


def summary(days: Optional[int] = 7, now: Optional[float] = None,
            path: Optional[Path] = None, include_samples: bool = False) -> Dict[str, Any]:
    """Aggregates for the last `days` days (None = all time) plus the previous
    period of the same length, so the UI can show trends."""
    now = now or time.time()
    events = load_events(path)
    if not include_samples:  # `python -m api.seed` events are for demos only
        events = [e for e in events if not e.get("sample")]
    if days:
        span = days * 86400
        current = [e for e in events if e["ts"] >= now - span]
        previous = [e for e in events if now - 2 * span <= e["ts"] < now - span]
    else:
        current, previous = events, []

    destinations: Counter = Counter(e["destination"] for e in current if e.get("destination"))
    regions: Counter = Counter()
    attractions: Counter = Counter()
    info: Dict[int, Dict[str, Any]] = {}
    for e in current:
        stops = e.get("stops") or [{"id": i} for i in e.get("attraction_ids", [])]
        for stop in stops:
            a = get_attraction(stop["id"])
            details = {"id": stop["id"], "name": stop.get("name") or (a.name if a else None),
                       "name_ar": stop.get("name_ar"), "region": stop.get("region") or (a.region if a else None),
                       "category": stop.get("category") or (a.category if a else None)}
            if not details["name"]:
                continue  # an old event for a place we can no longer name
            info.setdefault(stop["id"], details)
            attractions[stop["id"]] += 1
            if details["region"]:
                regions[details["region"]] += 1

    popular = [{**info[i], "count": count} for i, count in attractions.most_common(8)]

    return {
        "window_days": days,
        "current": _window_stats(current),
        "previous": _window_stats(previous) if previous else None,
        "destinations": _top(destinations, 6),
        "regions": _top(regions, 6),
        "attractions": popular,
    }
