from typing import Any, Dict, List, Optional

from agents.attractions import get_attraction
from agents.hours import DAYS, load_hours, resolve_day, to_minutes, to_text, get_windows
from agents.travel import calculate_travel_time, load_locations

STEP_MIN = 5            
MAX_WAIT_MIN = 90      
RANK_PENALTY_MIN = 15  
GREATER_CAIRO = {"Cairo", "Giza"} 

def area_of(region: str) -> str:
    return "Greater Cairo" if region in GREATER_CAIRO else region


def _fits(attraction_id: int, day_keys: List[str], start: int, duration: int) -> bool:
    """True if the visit fits inside an opening window on EVERY listed weekday."""
    end = start + duration
    for day in day_keys:
        windows = get_windows(attraction_id, day)
        if not windows:  
            return False
        if not any(opens <= start and end <= closes for opens, closes in windows):
            return False
    return True


def _earliest_start(attraction_id: int, day_keys: List[str], not_before: int,
                    day_end: int, duration: int) -> Optional[int]:
    start = not_before
    while start + duration <= day_end:
        if _fits(attraction_id, day_keys, start, duration):
            return start
        start += STEP_MIN
    return None


def _error(message: str) -> Dict[str, Any]:
    return {"ok": False, "error": message}


def build_itinerary(
    candidate_ids: List[Any],
    days: Any,
    first_day: Optional[str] = None,
    day_start: str = "09:00",
    day_end: str = "18:00",
    max_stops_per_day: int = 4,
) -> Dict[str, Any]:
    """Tool contract.

    candidate_ids:     attraction ids, MOST relevant first
    days:              number of days (1-14)
    first_day:         weekday name or ISO date of day 1 (optional, see module docstring)
    day_start/day_end: "HH:MM" window the traveller is available each day
    max_stops_per_day: sanity cap

    Returns {"ok": False, "error": ...} or
    {"ok": True, "days": [{"day", "weekday", "area", "stops": [...], "warnings": [...]}],
     "unscheduled": [{"attraction_id", "name", "reason"}], "warnings": [...]}
    """
    try:
        n_days = int(days)
    except (TypeError, ValueError):
        return _error(f"days must be a whole number, got {days!r}")
    if not 1 <= n_days <= 14:
        return _error("days must be between 1 and 14")

    try:
        start_min, end_min = to_minutes(day_start), to_minutes(day_end)
    except (AttributeError, ValueError):
        return _error("day_start and day_end must look like 'HH:MM'")
    if not 0 <= start_min < end_min <= 1440:
        return _error("day_start must be earlier than day_end")

    try:
        max_stops = int(max_stops_per_day)
    except (TypeError, ValueError):
        return _error("max_stops_per_day must be a whole number")
    if max_stops < 1:
        return _error("max_stops_per_day must be at least 1")

    if not isinstance(candidate_ids, (list, tuple)) or not candidate_ids:
        return _error("candidate_ids must be a non-empty list of attraction ids")
    ids: List[int] = []
    for raw_id in candidate_ids:
        try:
            attraction_id = int(raw_id)
        except (TypeError, ValueError):
            return _error(f"Invalid attraction id: {raw_id!r}")
        if get_attraction(attraction_id) is None:
            return _error(f"No attraction with id {attraction_id}")
        if attraction_id not in ids:  
            ids.append(attraction_id)

    first_index: Optional[int] = None
    if first_day is not None:
        day_key = resolve_day(first_day)
        if day_key is None:
            return _error(f"Could not understand first_day {first_day!r}; use a weekday name or YYYY-MM-DD")
        first_index = DAYS.index(day_key)

    def day_keys_for(day_number: int) -> List[str]:
        """Weekday(s) to check for day N (1-based). Unknown date -> all seven."""
        if first_index is None:
            return list(DAYS)
        return [DAYS[(first_index + day_number - 1) % 7]]
    viable_ids = [
        attraction_id for attraction_id in ids
        if any(
            _earliest_start(attraction_id, day_keys_for(d), start_min, end_min,
                            get_attraction(attraction_id).duration_min) is not None
            for d in range(1, n_days + 1)
        )
    ]

    candidates_by_area: Dict[str, List[int]] = {}
    for attraction_id in viable_ids:
        area = area_of(get_attraction(attraction_id).region)
        candidates_by_area.setdefault(area, []).append(attraction_id)

    areas = list(candidates_by_area)            # best-ranked area first
    chosen_areas = areas[:n_days]
    days_per_area = {area: 1 for area in chosen_areas}
    if chosen_areas:
        for _ in range(n_days - len(chosen_areas)):  # spare days go where most places are waiting
            busiest = max(chosen_areas, key=lambda a: len(candidates_by_area[a]) / days_per_area[a])
            days_per_area[busiest] += 1
    day_areas = [area for area in chosen_areas for _ in range(days_per_area[area])]

    remaining = {area: list(members) for area, members in candidates_by_area.items()}
    hours = load_hours()
    locations = load_locations()
    plan_days: List[Dict[str, Any]] = []
    any_travel = False

    for day_number, area in enumerate(day_areas, start=1):
        keys = day_keys_for(day_number)
        clock = start_min
        previous: Optional[int] = None
        stops: List[Dict[str, Any]] = []
        warnings: List[str] = []

        while len(stops) < max_stops:
            best = None
            for position, attraction_id in enumerate(remaining[area]):
                attraction = get_attraction(attraction_id)
                travel = 0
                if previous is not None:
                    trip = calculate_travel_time(previous, attraction_id)
                    if not trip["ok"] or trip["long_distance"]:
                        continue
                    travel = trip["minutes"]
                arrival = clock + travel
                start = _earliest_start(attraction_id, keys, arrival, end_min, attraction.duration_min)
                if start is None or start - arrival > MAX_WAIT_MIN:
                    continue
                score = travel + (start - arrival) + RANK_PENALTY_MIN * position
                if best is None or score < best[0]:
                    best = (score, attraction_id, start, travel)
            if best is None:
                break

            _, attraction_id, start, travel = best
            attraction = get_attraction(attraction_id)
            record = hours.get(attraction_id, {})
            stop = {
                "attraction_id": attraction_id,
                "name": attraction.name,
                "start": to_text(start),
                "end": to_text(start + attraction.duration_min),
                "duration_min": attraction.duration_min,
                "travel_from_previous_min": travel if previous is not None else None,
                "wait_min": start - (clock + travel),
                "hours_confidence": record.get("confidence", "unknown"),
                "hours_note": record.get("note", ""),
                "place_note": locations.get(attraction_id, {}).get("note", ""),
            }
            stops.append(stop)
            if previous is not None:
                any_travel = True
            if record.get("confidence") != "listed":
                warnings.append(f"Opening hours for {attraction.name} are not fully confirmed "
                                f"({record.get('note') or 'no details'}). Check before you go.")
            clock = start + attraction.duration_min
            previous = attraction_id
            remaining[area].remove(attraction_id)

        if not stops:
            warnings.append(f"Nothing could be scheduled in {area} on day {day_number} "
                            f"between {day_start} and {day_end}.")
        plan_days.append({
            "day": day_number,
            "weekday": keys[0] if first_index is not None else None,
            "area": area,
            "stops": stops,
            "warnings": warnings,
            "notes": [f"{s['name']}: {s['place_note']}" for s in stops if s["place_note"]],
        })

    scheduled = {stop["attraction_id"] for d in plan_days for stop in d["stops"]}
    days_of_area: Dict[str, List[int]] = {}
    for day_number, area in enumerate(day_areas, start=1):
        days_of_area.setdefault(area, []).append(day_number)

    unscheduled: List[Dict[str, Any]] = []
    for attraction_id in ids:
        if attraction_id in scheduled:
            continue
        attraction = get_attraction(attraction_id)
        area = area_of(attraction.region)
        if first_index is None:
            closed_reason = (f"Not scheduled: it is not open every day, or it does not fit between "
                             f"{day_start} and {day_end}. Give a travel date to check specific days.")
        else:
            closed_reason = (f"Not scheduled: it is closed on the travel day(s), or its visit does not "
                             f"fit between {day_start} and {day_end}.")

        if attraction_id not in viable_ids:
            reason = closed_reason
        elif area not in days_of_area:
            reason = f"Not included: it is in {area}, which does not fit in the {n_days} day(s) available."
        elif not any(
            _earliest_start(attraction_id, day_keys_for(d), start_min, end_min, attraction.duration_min) is not None
            for d in days_of_area[area]
        ):
            reason = closed_reason
        else:
            reason = "Not scheduled: no room left in the available days (time or stop limit)."
        unscheduled.append({"attraction_id": attraction_id, "name": attraction.name, "reason": reason})

    global_warnings: List[str] = []
    if not day_areas:
        global_warnings.append("None of the requested places could be scheduled in the time available.")
    if any_travel:
        global_warnings.append("Travel times are estimates (no live traffic data).")
    if len(set(day_areas)) > 1:
        global_warnings.append("Days are in different areas; travel between those areas is not included.")
    if first_index is None:
        global_warnings.append("No travel date given: only places open every day of the week were used.")

    return {"ok": True, "days": plan_days, "unscheduled": unscheduled, "warnings": global_warnings}

def time_day(ordered_ids: List[int], day_number: int, area: str, first_day: Optional[str] = None,
             day_start: str = "09:00", day_end: str = "18:00") -> Dict[str, Any]:
    """Re-time one day in a fixed order (used when the user edits a plan: "put X after Y").

    Same hard rules as build_itinerary: travel time between stops, opening windows on
    the weekday(s) the day can fall on, at most MAX_WAIT_MIN of waiting, and the
    day window. Stops that no longer fit are returned in `dropped` with a reason
    instead of being silently squeezed in.
    """
    first_index = DAYS.index(resolve_day(first_day)) if first_day and resolve_day(first_day) else None
    keys = list(DAYS) if first_index is None else [DAYS[(first_index + day_number - 1) % 7]]
    start_min, end_min = to_minutes(day_start), to_minutes(day_end)
    hours, locations = load_hours(), load_locations()
    clock, previous = start_min, None
    stops: List[Dict[str, Any]] = []
    warnings: List[str] = []
    dropped: List[Dict[str, Any]] = []
    for attraction_id in ordered_ids:
        attraction = get_attraction(attraction_id)
        if attraction is None:
            continue
        travel = 0
        if previous is not None:
            trip = calculate_travel_time(previous, attraction_id)
            if not trip["ok"] or trip["long_distance"]:
                dropped.append({"attraction_id": attraction_id, "name": attraction.name,
                                "reason": "Too far from the previous stop for the same day."})
                continue
            travel = trip["minutes"]
        arrival = clock + travel
        start = _earliest_start(attraction_id, keys, arrival, end_min, attraction.duration_min)
        if start is None or start - arrival > MAX_WAIT_MIN:
            dropped.append({"attraction_id": attraction_id, "name": attraction.name,
                            "reason": f"Doesn't fit in the day ({day_start}-{day_end}) at that point, "
                                      "or isn't open then."})
            continue
        record = hours.get(attraction_id, {})
        stops.append({
            "attraction_id": attraction_id, "name": attraction.name,
            "start": to_text(start), "end": to_text(start + attraction.duration_min),
            "duration_min": attraction.duration_min,
            "travel_from_previous_min": travel if previous is not None else None,
            "wait_min": start - arrival,
            "hours_confidence": record.get("confidence", "unknown"),
            "hours_note": record.get("note", ""),
            "place_note": locations.get(attraction_id, {}).get("note", ""),
        })
        if record.get("confidence") != "listed":
            warnings.append(f"Opening hours for {attraction.name} are not fully confirmed "
                            f"({record.get('note') or 'no details'}). Check before you go.")
        clock, previous = start + attraction.duration_min, attraction_id
    return {
        "day": {"day": day_number, "weekday": keys[0] if first_index is not None else None, "area": area,
                "stops": stops, "warnings": warnings,
                "notes": [f"{s['name']}: {s['place_note']}" for s in stops if s["place_note"]]},
        "dropped": dropped,
    }
