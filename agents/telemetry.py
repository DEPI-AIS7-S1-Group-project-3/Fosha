"""Per-request telemetry: what the LLM and the retriever did while answering one chat.

The LLM wrapper (agents/llm.py) and the retrieval adapter call record_llm() /
record_retrieval(). Outside a request (tests, the CLI) these calls do nothing. The API opens a
request scope, then stores the summary next to the analytics event, so the dashboard can show
LLM failure rate, fallback rate, p95 latency and retrieval quality drift.

    with telemetry.request() as metrics:
        result = plan_trip(...)
    metrics.summary()   # {"llm_calls": 2, "llm_failed": 0, "llm_fallbacks": 1, ...}

Uses contextvars, so concurrent requests never mix their numbers. No message text is recorded.
"""
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional

log = logging.getLogger("fosha")
_current: ContextVar[Optional["RequestMetrics"]] = ContextVar("fosha_request_metrics", default=None)


class RequestMetrics:
    def __init__(self) -> None:
        self.llm_calls: List[Dict[str, Any]] = []
        self.retrievals: List[Dict[str, Any]] = []

    def summary(self) -> Dict[str, Any]:
        distances = [r["top1_distance"] for r in self.retrievals if r["top1_distance"] is not None]
        return {
            "llm_calls": len(self.llm_calls),
            "llm_failed": sum(1 for c in self.llm_calls if not c["ok"]),
            # models that failed before one answered: > 0 means the primary model is unhealthy
            "llm_fallbacks": sum(c["failed_models"] for c in self.llm_calls),
            "llm_ms": sum(c["ms"] for c in self.llm_calls),
            "llm_models": [c["model"] for c in self.llm_calls if c["model"]],
            "retrievals": len(self.retrievals),
            "retrieval_empty": any(r["n_results"] == 0 for r in self.retrievals),
            "top1_distance": round(min(distances), 4) if distances else None,
        }


@contextmanager
def request() -> Iterator[RequestMetrics]:
    metrics = RequestMetrics()
    token = _current.set(metrics)
    try:
        yield metrics
    finally:
        _current.reset(token)


def record_llm(model: Optional[str], ok: bool, ms: int, failed_models: int = 0,
               error: Optional[str] = None) -> None:
    if not ok:
        log.warning("llm call failed after %d ms: %s", ms, (error or "")[:200])
    elif failed_models:
        log.warning("llm fell back to %s after %d failed model(s)", model, failed_models)
    metrics = _current.get()
    if metrics is not None:
        metrics.llm_calls.append({"model": model, "ok": ok, "ms": ms, "failed_models": failed_models})


def record_retrieval(top1_distance: Optional[float], n_results: int, dropped_too_far: int = 0) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.retrievals.append({"top1_distance": top1_distance, "n_results": n_results,
                                   "dropped_too_far": dropped_too_far})


def configure_logging() -> None:
    """One readable line per event on stderr. Level from LOG_LEVEL (default INFO). Idempotent."""
    if log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(handler)
    log.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
    log.propagate = False
