from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List
import json
import math

from agents.attractions import load_attractions

LOCATIONS_PATH = Path(__file__).resolve().parent / "data" / "locations.json"
ROAD_FACTOR = 1.3
OVERHEAD_MIN = 10
LONG_DISTANCE_KM = 150  # beyond this, two stops cannot share a normal sightseeing day


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (straight-line) distance between two points, in km."""
    earth_radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))


def speed_kmh(straight_km: float) -> float:
    if straight_km < 5:
        return 20.0
    if straight_km <= 60:
        return 30.0
    return 70.0


@lru_cache(maxsize=1)
def load_locations() -> Dict[int, Dict[str, Any]]:
    with open(LOCATIONS_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {int(attraction_id): record for attraction_id, record in raw.items()}


def calculate_travel_time(from_id: Any, to_id: Any) -> Dict[str, Any]:
    """Tool contract. Estimated travel time between two attractions.

    Returns {"ok": False, "error": ...} for bad input, otherwise
    {"ok": True, "minutes": 40, "straight_km": 12.2, "road_km_estimate": 15.9,
     "estimate": True, "long_distance": False, "note": "..."}
    long_distance=True means the scheduler must not put both stops on the same day.
    """
    try:
        id_a, id_b = int(from_id), int(to_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": f"Invalid attraction ids: {from_id!r}, {to_id!r}"}

    locations = load_locations()
    for wanted in (id_a, id_b):
        if wanted not in locations:
            return {"ok": False, "error": f"No coordinates for attraction id {wanted}"}

    a, b = locations[id_a], locations[id_b]
    straight = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
    road = straight * ROAD_FACTOR
    if id_a == id_b:
        minutes = 0
    else:
        raw_minutes = road / speed_kmh(straight) * 60 + OVERHEAD_MIN
        minutes = int(5 * round(raw_minutes / 5))

    notes = [n for n in (a.get("note"), b.get("note")) if n]
    return {
        "ok": True,
        "minutes": minutes,
        "straight_km": round(straight, 1),
        "road_km_estimate": round(road, 1),
        "estimate": True,
        "long_distance": straight > LONG_DISTANCE_KM,
        "note": " | ".join(dict.fromkeys(notes)),  # de-duplicated, order kept
    }


def validate_locations() -> List[str]:
    """Consistency check for locations.json. Empty list = all good."""
    problems: List[str] = []
    locations = load_locations()
    raw_ids = set(load_attractions())
    for missing in sorted(raw_ids - set(locations)):
        problems.append(f"id {missing}: no coordinates")
    for extra in sorted(set(locations) - raw_ids):
        problems.append(f"id {extra}: in locations.json but not in raw_attractions.json")
    for attraction_id, record in locations.items():
        try:
            lat, lon = float(record["lat"]), float(record["lon"])
        except (KeyError, TypeError, ValueError):
            problems.append(f"id {attraction_id}: lat/lon missing or not numbers")
            continue
        if not (21.5 <= lat <= 32.0 and 24.5 <= lon <= 37.0):  # rough bounding box of Egypt
            problems.append(f"id {attraction_id}: ({lat}, {lon}) is outside Egypt")
    return problems