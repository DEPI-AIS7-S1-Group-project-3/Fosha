"""In-memory usage counters for the dashboard (Member 4) and evaluation (Member 5).
Counters reset when the server restarts.
"""
import threading
import time
from collections import Counter
from typing import Any, Dict, List, Optional


def _top(counter: Counter, n: int) -> List[Dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(n)]


class Analytics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started = time.time()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.total_queries = 0
            self.errors = 0
            self._total_ms = 0.0
            self.statuses: Counter = Counter()
            self.languages: Counter = Counter()
            self.regions: Counter = Counter()
            self.attractions: Counter = Counter()
            self.interests: Counter = Counter()

    def record_chat(self, result: Dict[str, Any], elapsed_ms: float) -> None:
        intent = result.get("intent") or {}
        with self._lock:
            self.total_queries += 1
            self._total_ms += elapsed_ms
            self.statuses[result.get("status", "unknown")] += 1
            self.languages[result.get("language", "unknown")] += 1
            if intent.get("region"):
                self.regions[intent["region"]] += 1
            elif intent.get("unsupported_region"):
                self.regions[f"{intent['unsupported_region']} (unsupported)"] += 1
            for interest in intent.get("interests") or []:
                self.interests[str(interest).lower()] += 1
            for day in (result.get("itinerary") or {}).get("days", []):
                for stop in day.get("stops", []):
                    self.attractions[stop.get("name", "?")] += 1

    def record_error(self, elapsed_ms: Optional[float] = None) -> None:
        with self._lock:
            self.total_queries += 1
            self.errors += 1
            if elapsed_ms is not None:
                self._total_ms += elapsed_ms

    def snapshot(self, cache_stats: Dict[str, Any], top_n: int = 10) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_queries": self.total_queries,
                "errors": self.errors,
                "avg_response_ms": round(self._total_ms / self.total_queries, 1) if self.total_queries else 0.0,
                "uptime_seconds": int(time.time() - self._started),
                "statuses": dict(self.statuses),
                "languages": dict(self.languages),
                "top_regions": _top(self.regions, top_n),
                "top_attractions": _top(self.attractions, top_n),
                "top_interests": _top(self.interests, top_n),
                "cache": cache_stats,
            }
