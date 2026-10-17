from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json

from agents.attractions import get_attraction, load_attractions

HOURS_PATH = Path(__file__).resolve().parent / "data" / "attraction_extras.json"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # same order as date.weekday()


def to_minutes(text: str) -> int:
    """'09:30' -> 570. '24:00' -> 1440 (end of day)."""
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def to_text(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def resolve_day(value: Any) -> Optional[str]:
    """'Friday', 'fri', 'Thurs' or '2026-10-23' -> 'fri' / 'thu'. None if not understood."""
    text = str(value).strip().lower()
    if text.isalpha() and text[:3] in DAYS:
        return text[:3]
    try:
        return DAYS[date.fromisoformat(text).weekday()]
    except ValueError:
        return None


@lru_cache(maxsize=1)
def load_hours() -> Dict[int, Dict[str, Any]]:
    with open(HOURS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(attraction_id): record for attraction_id, record in raw.items()}


def get_windows(attraction_id: int, day: str) -> Optional[List[Tuple[int, int]]]:
    """Opening windows (minutes since midnight) for that weekday.
    [] means closed all day. None means we have no hours record at all."""
    record = load_hours().get(attraction_id)
    if record is None:
        return None
    windows = record.get("overrides", {}).get(day, record["default"])
    return [(to_minutes(opens), to_minutes(closes)) for opens, closes in windows]


def check_opening_hours(
    attraction_id: Any,
    day: Any,
    start: str,
    duration_min: Optional[int] = None,
) -> Dict[str, Any]:
    """Tool contract. Can this visit happen?

    attraction_id: id of the place
    day:           weekday name ("Friday") or an ISO date ("2026-10-23")
    start:         arrival time "HH:MM" (24-hour)
    duration_min:  how long we plan to stay; defaults to the attraction's usual visit time

    Returns {"ok": False, "error": ...} for bad input, otherwise
    {"ok": True, "open": True/False/None, "confidence": ..., "windows": ["09:00-17:00"],
     "reason": ..., "note": ...}
    """
    try:
        wanted_id = int(attraction_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": f"Invalid attraction id: {attraction_id!r}"}
    attraction = get_attraction(wanted_id)
    if attraction is None:
        return {"ok": False, "error": f"No attraction with id {wanted_id}"}

    day_key = resolve_day(day)
    if day_key is None:
        return {"ok": False, "error": f"Could not understand day {day!r}; use a weekday name or YYYY-MM-DD"}

    try:
        start_min = to_minutes(start)
    except (AttributeError, ValueError):
        return {"ok": False, "error": f"Could not understand start time {start!r}; use HH:MM"}

    try:
        stay = int(duration_min) if duration_min is not None else attraction.duration_min
    except (TypeError, ValueError):
        return {"ok": False, "error": f"Invalid duration: {duration_min!r}"}
    end_min = start_min + stay

    windows = get_windows(wanted_id, day_key)
    if windows is None:
        return {"ok": True, "open": None, "confidence": "unknown", "windows": [], "note": "",
                "reason": "No structured opening hours for this attraction, so it cannot be confirmed."}

    record = load_hours()[wanted_id]
    window_text = [f"{to_text(a)}-{to_text(b)}" for a, b in windows]
    base = {"ok": True, "confidence": record["confidence"], "windows": window_text, "note": record.get("note", "")}

    visit = f"{to_text(start_min)}-{to_text(end_min)}"
    if not windows:
        return {**base, "open": False, "reason": f"Closed on {day_key.upper()}."}
    if any(opens <= start_min and end_min <= closes for opens, closes in windows):
        return {**base, "open": True, "reason": f"Visit {visit} fits inside opening hours ({', '.join(window_text)})."}
    return {**base, "open": False,
            "reason": f"Visit {visit} does not fit inside opening hours on {day_key.upper()} ({', '.join(window_text)})."}


def validate_hours() -> List[str]:
    """Consistency check for the hours file. Empty list = all good."""
    problems: List[str] = []
    hours = load_hours()
    raw_ids = set(load_attractions())
    for missing in sorted(raw_ids - set(hours)):
        problems.append(f"id {missing}: no entry in attraction_extras.json")
    for extra in sorted(set(hours) - raw_ids):
        problems.append(f"id {extra}: in attraction_extras.json but not in raw_attractions.json")
    for attraction_id, record in hours.items():
        if record.get("confidence") not in ("listed", "uncertain"):
            problems.append(f"id {attraction_id}: confidence must be 'listed' or 'uncertain'")
        blocks = [("default", record.get("default", []))]
        for day_key, day_windows in record.get("overrides", {}).items():
            if day_key not in DAYS:
                problems.append(f"id {attraction_id}: unknown override day {day_key!r}")
            blocks.append((day_key, day_windows))
        for label, windows in blocks:
            try:
                parsed = [(to_minutes(a), to_minutes(b)) for a, b in windows]
            except (ValueError, TypeError):
                problems.append(f"id {attraction_id} ({label}): unreadable time in {windows}")
                continue
            for opens, closes in parsed:
                if not 0 <= opens < closes <= 1440:
                    problems.append(f"id {attraction_id} ({label}): bad window {to_text(opens)}-{to_text(closes)}")
    return problems