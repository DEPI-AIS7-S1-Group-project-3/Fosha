from fastapi import APIRouter

from agents.scheduler import build_itinerary
from backend.errors import bad_request
from backend.schemas import ItineraryRequest, ItineraryResponse
from backend.services.itinerary import add_ticket_prices

router = APIRouter(tags=["itinerary"])


@router.post("/itinerary", response_model=ItineraryResponse)
def create_itinerary(body: ItineraryRequest) -> dict:
    """Build a schedule from attractions the user picked (no LLM, instant).
    Used by the UI when the user edits a plan by hand: add/remove a place, change days.
    Every stop respects opening hours, visit duration and travel time."""
    result = build_itinerary(body.attraction_ids, body.days, first_day=body.first_day,
                             day_start=body.day_start, day_end=body.day_end,
                             max_stops_per_day=body.max_stops_per_day)
    if not result["ok"]:
        raise bad_request(result["error"])

    add_ticket_prices(result, body.visitor_type)
    return result
