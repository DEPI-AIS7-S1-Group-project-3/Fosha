from typing import Any, Dict, Optional

from agents.pricing import check_ticket_price


def add_ticket_prices(itinerary: Optional[Dict[str, Any]], visitor_type: Optional[str]) -> None:
    """Put ticket_price_egp / price_note on every stop, in place.

    The agent only writes prices into the reply text; the frontend needs them in
    the structured itinerary too. Safe to call twice (cached results).
    """
    if not itinerary or not visitor_type:
        return
    for day in itinerary.get("days", []):
        for stop in day.get("stops", []):
            price = check_ticket_price(stop.get("attraction_id"), visitor_type)
            if price["ok"]:
                stop["ticket_price_egp"] = price["price_egp"]
                stop["price_note"] = price["price_note"]
