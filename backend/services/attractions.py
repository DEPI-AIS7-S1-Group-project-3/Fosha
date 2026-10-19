"""Read-only attraction data for the API, built from Member 2's data layer
(agents.attractions / hours / travel). No LLM and no vector search involved.

Also flags missing or possibly outdated information, so the frontend can show
"verify before you go" instead of presenting old data as fact.
"""
from datetime import date
from typing import Any, Dict, List, Optional

from agents.attractions import Attraction, get_attraction, load_attractions
from agents.hours import load_hours
from agents.travel import load_locations


def _location(attraction_id: int) -> Optional[Dict[str, Any]]:
    record = load_locations().get(attraction_id)
    if not record:
        return None
    return {"lat": record["lat"], "lon": record["lon"], "note": record.get("note", "")}


def summary(attraction: Attraction) -> Dict[str, Any]:
    return {
        "id": attraction.id, "name": attraction.name, "city": attraction.city,
        "region": attraction.region, "category": attraction.category,
        "duration_min": attraction.duration_min,
        "price_egyptian_egp": attraction.price_egyptian_egp,
        "price_foreigner_egp": attraction.price_foreigner_egp,
        "location": _location(attraction.id),
    }


def freshness(attraction: Attraction, stale_after_days: int, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    warnings: List[str] = []
    try:
        age: Optional[int] = (today - date.fromisoformat(attraction.last_verified)).days
    except ValueError:
        age = None
        warnings.append("No valid verification date; information may be outdated.")
    stale = age is None or age > stale_after_days
    if age is not None and stale:
        warnings.append(f"Last verified {age} days ago; hours and prices may have changed.")

    hours = load_hours().get(attraction.id)
    if hours is None:
        warnings.append("No structured opening hours; only the text description is available.")
    elif hours.get("confidence") != "listed":
        warnings.append("Opening hours are not fully confirmed; check before you go.")
    if attraction.price_egyptian_egp == 0 or attraction.price_foreigner_egp == 0:
        warnings.append("A ticket price of 0 EGP may mean free entry or that no price was recorded.")
    if load_locations().get(attraction.id) is None:
        warnings.append("No map location recorded.")

    return {"last_verified": attraction.last_verified, "source_url": attraction.source_url,
            "days_since_verified": age, "stale": stale, "warnings": warnings}


def detail(attraction: Attraction, stale_after_days: int) -> Dict[str, Any]:
    hours = load_hours().get(attraction.id) or {}
    return {
        **summary(attraction),
        "description": attraction.description,
        "opening_hours": {
            "text": attraction.opening_hours_text,
            "default": hours.get("default", []),
            "overrides": hours.get("overrides", {}),
            "confidence": hours.get("confidence", "unknown"),
            "note": hours.get("note", ""),
        },
        "freshness": freshness(attraction, stale_after_days),
    }


def list_attractions(region: Optional[str] = None, category: Optional[str] = None,
                     q: Optional[str] = None) -> List[Attraction]:
    items = sorted(load_attractions().values(), key=lambda a: a.id)
    if region:
        wanted = region.strip().lower()
        # "Cairo" means Greater Cairo everywhere else in the project (Pyramids are filed under Giza).
        regions = {"cairo", "giza"} if wanted in ("cairo", "greater cairo") else {wanted}
        items = [a for a in items if a.region.lower() in regions]
    if category:
        items = [a for a in items if a.category.lower() == category.strip().lower()]
    if q:
        needle = q.strip().lower()
        items = [a for a in items if needle in a.name.lower() or needle in a.description.lower()]
    return items


def find(attraction_id: int) -> Optional[Attraction]:
    return get_attraction(attraction_id)


def regions() -> List[str]:
    return sorted({a.region for a in load_attractions().values()})


def categories() -> List[str]:
    return sorted({a.category for a in load_attractions().values()})
