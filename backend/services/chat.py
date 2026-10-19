"""The integration point between the API and the agent (agents.planner.plan_trip).

Adds on top of the agent: caching of repeated queries, session handling for
clarification follow-ups, analytics, and mapping agent errors to HTTP errors.
"""
import time
from datetime import date
from typing import Any, Callable, Dict, Optional

from backend.errors import from_agent_error
from backend.services.analytics import Analytics
from backend.services.cache import TTLCache, make_key
from backend.services.sessions import SessionStore

PlanFn = Callable[[str], Dict[str, Any]]


def _default_plan_fn() -> PlanFn:
    from agents.planner import plan_trip  # imported lazily so tests never touch Gemini

    return plan_trip


class ChatService:
    def __init__(self, cache: TTLCache, sessions: SessionStore, analytics: Analytics,
                 plan_fn: Optional[PlanFn] = None):
        self.cache = cache
        self.sessions = sessions
        self.analytics = analytics
        self._plan_fn = plan_fn

    @property
    def plan_fn(self) -> PlanFn:
        if self._plan_fn is None:
            self._plan_fn = _default_plan_fn()
        return self._plan_fn

    def chat(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Blocking (LLM + retrieval). FastAPI runs it in a worker thread."""
        started = time.perf_counter()
        session = self.sessions.get_or_create(session_id)
        message = message.strip()

        # Answer to a clarifying question -> send it with the original request.
        effective = f"{session.pending_request}\n{message}" if session.pending_request else message

        # The date is part of the key: the agent resolves "next Friday" against today.
        key = make_key(date.today().isoformat(), effective)
        result = self.cache.get(key)
        cached = result is not None
        if not cached:
            result = self.plan_fn(effective)
            if not result.get("ok"):
                self.analytics.record_error((time.perf_counter() - started) * 1000)
                raise from_agent_error(str(result.get("error", "unknown error")))
            self.cache.set(key, result)

        session.pending_request = effective if result["status"] == "needs_clarification" else None
        session.add("user", message)
        session.add("assistant", result["reply"])
        self.analytics.record_chat(result, (time.perf_counter() - started) * 1000)

        return {
            "session_id": session.id,
            "status": result["status"],
            "language": result["language"],
            "reply": result["reply"],
            "intent": result.get("intent") or {},
            "itinerary": result.get("itinerary"),
            "missing": result.get("missing"),
            "used_fallback": result.get("used_fallback"),
            "cached": cached,
        }
