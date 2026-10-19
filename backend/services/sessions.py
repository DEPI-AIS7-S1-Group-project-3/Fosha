"""Minimal per-conversation state, kept in memory.

The agent (agents/planner.py) has no memory yet, so for now the backend only does
one thing with it: when the agent asked a clarifying question ("How many days?"),
the next message is sent together with the original request, so a reply like
"3 days" completes the trip request instead of starting a new one.

When Member 2 adds real session memory, this store keeps the history and the
`pending` logic can be removed.
"""
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

MAX_HISTORY = 20


@dataclass
class Session:
    id: str
    updated: float
    history: List[Dict[str, str]] = field(default_factory=list)
    pending_request: Optional[str] = None  # original message while a clarification is open

    def add(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text})
        del self.history[:-MAX_HISTORY]


class SessionStore:
    def __init__(self, ttl_seconds: int = 3600, clock=time.monotonic):
        self.ttl = ttl_seconds
        self._clock = clock
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: Optional[str]) -> Session:
        now = self._clock()
        with self._lock:
            self._expire(now)
            session = self._sessions.get(session_id) if session_id else None
            if session is None:
                session = Session(id=session_id or uuid.uuid4().hex, updated=now)
                self._sessions[session.id] = session
            session.updated = now
            return session

    def get(self, session_id: str) -> Optional[Session]:
        with self._lock:
            self._expire(self._clock())
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def __len__(self) -> int:
        return len(self._sessions)

    def _expire(self, now: float) -> None:
        for key in [k for k, s in self._sessions.items() if now - s.updated > self.ttl]:
            del self._sessions[key]
