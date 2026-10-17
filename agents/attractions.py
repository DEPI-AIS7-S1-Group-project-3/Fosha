"""Attraction facts for the travel agent.
trustworthy FACTS about a place (hours text, prices, visit duration, source) by looking it up by id
"""
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, Dict, Optional
import json

from rag.config import RAW_DATA_PATH 


@dataclass(frozen=True)
class Attraction:
    id: int
    name: str
    city: str
    region: str
    category: str
    description: str
    opening_hours_text: str  
    price_egyptian_egp: float
    price_foreigner_egp: float
    duration_min: int
    source_url: str
    last_verified: str


@lru_cache(maxsize=1)
def load_attractions() -> Dict[int, Attraction]:
    """Read raw_attractions.json once and return {id: Attraction}."""
    with open(RAW_DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    attractions: Dict[int, Attraction] = {}
    for item in raw:
        attraction = Attraction(
            id=int(item["id"]),
            name=item["name"],
            city=item["city"],
            region=item["region"],
            category=item["category"],
            description=item["description"],
            opening_hours_text=item["opening_hours"],
            price_egyptian_egp=float(item["ticket_price_egyptian_adult_egp"]),
            price_foreigner_egp=float(item["ticket_price_foreigner_adult_egp"]),
            duration_min=int(item["estimated_visit_duration_min"]),
            source_url=item["source_url"],
            last_verified=item["last_verified"],
        )
        attractions[attraction.id] = attraction
    return attractions


def get_attraction(attraction_id: int) -> Optional[Attraction]:
    """Internal helper for our own Python code. Returns None if the id is unknown."""
    return load_attractions().get(attraction_id)


def get_attraction_details(attraction_id: Any) -> Dict[str, Any]:
    """Tool contract (what the LLM will call).

    Always returns a dict with an "ok" flag, so the agent never has to guess
    whether a call worked:
        {"ok": True,  "attraction": {...all fields...}}
        {"ok": False, "error": "human-readable reason"}
    """
    try:
        wanted_id = int(attraction_id)  
    except (TypeError, ValueError):
        return {"ok": False, "error": f"Invalid attraction id: {attraction_id!r}"}

    attraction = get_attraction(wanted_id)
    if attraction is None:
        return {"ok": False, "error": f"No attraction with id {wanted_id}"}
    return {"ok": True, "attraction": asdict(attraction)}