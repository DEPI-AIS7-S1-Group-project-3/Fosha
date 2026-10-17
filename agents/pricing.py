from typing import Any, Dict, Optional
from agents.attractions import get_attraction

def resolve_visitor_type(value: Any) -> Optional[str]:
    """'Egyptian' / 'local' -> 'egyptian'; 'foreigner' / 'tourist' -> 'foreigner'; else None."""
    text = str(value).strip().lower()
    # Check foreign first: "non-egyptian" contains the word "egyptian".
    if any(word in text for word in ("foreign", "tourist", "non-egypt", "non egypt")):
        return "foreigner"
    if "egypt" in text or "local" in text:
        return "egyptian"
    return None


def check_ticket_price(attraction_id: Any, visitor_type: Any = None) -> Dict[str, Any]:
    """Tool contract. Adult ticket price for one visitor.

    visitor_type: "egyptian" or "foreigner". If the user has not said which, the
    agent must ask; this tool refuses to guess.

    Returns {"ok": False, "error": ...} or
    {"ok": True, "name": ..., "visitor_type": ..., "price_egp": 550.0, "ticket": "adult",
     "price_note": ..., "source_url": ..., "last_verified": ...}
    """
    try:
        wanted_id = int(attraction_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": f"Invalid attraction id: {attraction_id!r}"}
    attraction = get_attraction(wanted_id)
    if attraction is None:
        return {"ok": False, "error": f"No attraction with id {wanted_id}"}

    if visitor_type is None:
        return {"ok": False, "error": "visitor_type is required ('egyptian' or 'foreigner'). Ask the user which applies."}
    visitor = resolve_visitor_type(visitor_type)
    if visitor is None:
        return {"ok": False, "error": f"Could not understand visitor_type {visitor_type!r}; use 'egyptian' or 'foreigner'."}

    price = attraction.price_egyptian_egp if visitor == "egyptian" else attraction.price_foreigner_egp
    if price == 0:
        note = ("Listed as 0 EGP. That may mean free entry or that no price was recorded; "
                "verify on the source page before telling the user it is free.")
    else:
        note = "Adult ticket only. Prices change; verify on the source page."

    return {
        "ok": True,
        "attraction_id": wanted_id,
        "name": attraction.name,
        "visitor_type": visitor,
        "price_egp": price,
        "ticket": "adult",
        "price_note": note,
        "source_url": attraction.source_url,
        "last_verified": attraction.last_verified,
    }