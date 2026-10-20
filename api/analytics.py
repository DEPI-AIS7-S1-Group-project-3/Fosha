"""Query log + aggregates for the Fosha insights dashboard (/dashboard).

Every /api/v1/chat call appends one JSON line to data/analytics.jsonl (gitignored).
The dashboard reads the same file, so numbers survive a server restart.
The raw message text is NOT stored, only what the dashboard needs.
"""
import json
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from agents.attractions import get_attraction

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "analytics.jsonl"
_lock = threading.Lock()


def record_event(result: Dict[str, Any], cached: bool, response_ms: int,
                 path: Optional[Path] = None) -> Dict[str, Any]:
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
        "cached": cached,
        "response_ms": response_ms,
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


def _window_stats(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    events = list(events)
    total = len(events)
    languages = Counter(e["language"] for e in events)
    cached = sum(1 for e in events if e.get("cached"))
    fresh_times = [e["response_ms"] for e in events if not e.get("cached")]
    return {
        "total_queries": total,
        "cache_hit_rate": round(cached / total, 4) if total else 0.0,
        "avg_response_ms": round(sum(fresh_times) / len(fresh_times)) if fresh_times else 0,
        "languages": {"en": languages.get("en", 0), "ar": languages.get("ar", 0)},
        "planned": sum(1 for e in events if e.get("status") == "planned"),
    }


def summary(days: Optional[int] = 7, now: Optional[float] = None,
            path: Optional[Path] = None) -> Dict[str, Any]:
    """Aggregates for the last `days` days (None = all time) plus the previous
    period of the same length, so the UI can show trends."""
    now = now or time.time()
    events = load_events(path)
    if days:
        span = days * 86400
        current = [e for e in events if e["ts"] >= now - span]
        previous = [e for e in events if now - 2 * span <= e["ts"] < now - span]
    else:
        current, previous = events, []

    destinations: Counter = Counter(e["destination"] for e in current if e.get("destination"))
    regions: Counter = Counter()
    attractions: Counter = Counter()
    for e in current:
        for attraction_id in e.get("attraction_ids", []):
            attraction = get_attraction(attraction_id)
            if attraction:
                attractions[attraction_id] += 1
                regions[attraction.region] += 1

    popular = []
    for attraction_id, count in attractions.most_common(8):
        a = get_attraction(attraction_id)
        popular.append({"id": a.id, "name": a.name, "region": a.region,
                        "category": a.category, "count": count})

    return {
        "window_days": days,
        "current": _window_stats(current),
        "previous": _window_stats(previous) if previous else None,
        "destinations": _top(destinations, 6),
        "regions": _top(regions, 6),
        "attractions": popular,
    }
