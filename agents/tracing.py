"""Optional Langfuse tracing (self-hosted). Off unless you turn it on; never sends message text.

What it adds on top of agents/telemetry.py: telemetry gives per-request NUMBERS for the
dashboard; Langfuse gives a per-request TRACE (which step ran, how long it took, which model
answered after how many fallbacks, token counts) that you can click through in its UI.

    chat (trace)
    ├── intent.extract      span
    │   └── llm.generate    generation (model, tokens, fallbacks)
    ├── retrieval.search    retriever  (n_results, top1_distance, dropped_too_far)
    ├── schedule            span
    └── reply.write         span
        └── llm.generate    generation

Turn it on (see the README, "Tracing with Langfuse"):
    uv sync --extra observability
    LANGFUSE_PUBLIC_KEY=pk-lf-...  LANGFUSE_SECRET_KEY=sk-lf-...  LANGFUSE_BASE_URL=http://localhost:3000

Rules this file keeps:
  * No keys, no package, LANGFUSE_TRACING_ENABLED=false, or a failed start -> every helper is a
    no-op, so the app and the tests behave exactly as before.
  * Message text is NEVER sent. Callers pass no prompt, reply or query text, only counts and
    flags. As a second lock, the client-wide mask below blanks every string that is not on a
    short allow-list of harmless fields (model name, status, language...).
  * Tracing can never break a request: every Langfuse call is wrapped, and errors are logged once.
"""
import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

log = logging.getLogger("fosha")

MASKED = "[masked]"
# String values under these keys are kept; every other string is replaced by MASKED.
SAFE_STRING_KEYS = frozenset({
    "model", "provider", "status", "language", "mode", "search_mode", "kind", "level", "task",
    "region_filter", "category_filter",
})

_lock = threading.Lock()
_client_obj: Any = None
_client_ready = False  # True once we have tried to build the client (success or not)


# ---------------------------------------------------------------- masking
def scrub(value: Any, key: Optional[str] = None) -> Any:
    """Keep numbers, booleans and None; keep a string only under a SAFE_STRING_KEYS key;
    blank everything else. Works through dicts and lists."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if key in SAFE_STRING_KEYS else MASKED
    if isinstance(value, dict):
        return {str(k): scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [scrub(v, key) for v in value]
    return MASKED


def mask(*, data: Any, **_: Any) -> Any:
    """Langfuse `mask` hook: runs on every input, output and metadata before it leaves the app."""
    return scrub(data)


# ---------------------------------------------------------------- client
def _wanted() -> bool:
    if os.environ.get("LANGFUSE_TRACING_ENABLED", "").strip().lower() in ("0", "false", "no", "off"):
        return False
    return bool(os.environ.get("LANGFUSE_PUBLIC_KEY", "").strip()
                and os.environ.get("LANGFUSE_SECRET_KEY", "").strip())


def _client() -> Any:
    """The shared Langfuse client, or None when tracing is off or could not start."""
    global _client_obj, _client_ready
    if _client_ready:
        return _client_obj
    with _lock:
        if _client_ready:
            return _client_obj
        _client_ready = True
        if not _wanted():
            return None
        try:
            from langfuse import Langfuse
        except ImportError:
            log.warning("Langfuse keys are set but the package is missing: uv sync --extra observability")
            return None
        try:
            base_url = (os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST")
                        or "http://localhost:3000").strip()
            _client_obj = Langfuse(
                public_key=os.environ["LANGFUSE_PUBLIC_KEY"].strip(),
                secret_key=os.environ["LANGFUSE_SECRET_KEY"].strip(),
                base_url=base_url,
                mask=mask,
                environment=os.environ.get("LANGFUSE_TRACING_ENVIRONMENT") or None,
            )
            log.info("Langfuse tracing on -> %s", base_url)
        except Exception as exc:  # bad config must not stop the app
            log.warning("Langfuse could not start, tracing is off: %s", exc)
            _client_obj = None
        return _client_obj


def enabled() -> bool:
    return _client() is not None


def reset() -> None:
    """Forget the client (tests, or after changing the environment)."""
    global _client_obj, _client_ready
    with _lock:
        _client_obj, _client_ready = None, False


def shutdown() -> None:
    """Send what is still queued. Call when the server stops."""
    client = _client_obj
    if client is None:
        return
    try:
        client.shutdown()
    except Exception as exc:
        log.warning("Langfuse shutdown failed: %s", exc)


# ---------------------------------------------------------------- spans
class Handle:
    """What `with tracing.observation(...) as obs` gives you. update() never raises."""

    def __init__(self, observation: Any = None, client: Any = None) -> None:
        self._obs = observation
        self._client = client

    def update(self, **fields: Any) -> None:
        """metadata, model, usage_details, level, status_message ... (see Langfuse's update())."""
        if self._obs is None:
            return
        try:
            self._obs.update(**{k: v for k, v in fields.items() if v is not None})
        except Exception as exc:
            log.debug("Langfuse update failed: %s", exc)

    def score(self, name: str, value: float, comment: Optional[str] = None) -> None:
        """Numeric score on the whole trace this observation belongs to."""
        if self._obs is None or self._client is None or value is None:
            return
        try:
            self._obs.score_trace(name=name, value=float(value), data_type="NUMERIC", comment=comment)
        except Exception as exc:
            log.debug("Langfuse score failed: %s", exc)


_NOOP = Handle()


@contextmanager
def observation(name: str, as_type: str = "span", **metadata: Any) -> Iterator[Handle]:
    """One step of a trace. Yields a Handle; errors raised by your code pass through untouched."""
    client = _client()
    if client is None:
        yield _NOOP
        return
    try:
        manager = client.start_as_current_observation(
            name=name, as_type=as_type, metadata=scrub(metadata) if metadata else None)
        obs = manager.__enter__()
    except Exception as exc:
        log.debug("Langfuse could not open %s: %s", name, exc)
        yield _NOOP
        return
    try:
        yield Handle(obs, client)
    finally:
        try:
            manager.__exit__(None, None, None)
        except Exception as exc:
            log.debug("Langfuse could not close %s: %s", name, exc)


@contextmanager
def trace(name: str, tags: Optional[List[str]] = None, **metadata: Any) -> Iterator[Handle]:
    """The root of a trace (one chat request). Same as observation(), plus a trace name and tags."""
    client = _client()
    if client is None:
        yield _NOOP
        return
    try:
        from langfuse import propagate_attributes
        attrs = propagate_attributes(trace_name=name, tags=tags or None)
        attrs.__enter__()
    except Exception as exc:
        log.debug("Langfuse could not name the trace: %s", exc)
        attrs = None
    try:
        with observation(name, **metadata) as root:
            yield root
    finally:
        if attrs is not None:
            try:
                attrs.__exit__(None, None, None)
            except Exception as exc:
                log.debug("Langfuse could not close the trace attributes: %s", exc)
