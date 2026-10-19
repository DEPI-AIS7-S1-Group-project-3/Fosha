"""Small thread-safe TTL + LRU cache for repeated queries.

In-process on purpose: one worker is enough for the capstone, and it has no
infrastructure to run. If we ever run several workers, swap this class for a
Redis-backed one with the same get/set/stats methods.
"""
import hashlib
import re
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_query(text: str) -> str:
    """'  2 Days in CAIRO!! ' and '2 days in cairo' should hit the same entry."""
    text = text.translate(_ARABIC_DIGITS).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def make_key(*parts: str) -> str:
    raw = "\x1f".join(normalize_query(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TTLCache:
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 512, clock=time.monotonic):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._data: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._data.get(key)
            if item is None or item[0] < self._clock():
                if item is not None:
                    del self._data[key]
                self.misses += 1
                return None
            self._data.move_to_end(key)
            self.hits += 1
            return item[1]

    def set(self, key: str, value: Any) -> None:
        if self.ttl <= 0 or self.max_entries <= 0:
            return
        with self._lock:
            self._data[key] = (self._clock() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self.hits = self.misses = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            return {"hits": self.hits, "misses": self.misses,
                    "hit_rate": round(self.hits / total, 4) if total else 0.0,
                    "entries": len(self._data)}
