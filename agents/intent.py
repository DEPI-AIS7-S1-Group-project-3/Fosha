import json
import re
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from agents.attractions import load_attractions
from agents.hours import resolve_day
from agents.pricing import resolve_visitor_type

LLMFn = Callable[..., Dict[str, Any]]


def known_regions() -> List[str]:
    """Regions that exist in the data. 'Cairo' also covers Giza (see retrieval_adapter)."""
    return sorted({a.region for a in load_attractions().values()})


def _system_prompt() -> str:
    return (
        "You extract trip-planning details for an Egypt travel assistant. "
        "Reply with ONE JSON object and nothing else.\n"
        "Keys:\n"
        '  task: "plan_trip" if the user wants a trip/itinerary/places to visit, otherwise "other"\n'
        '  language: "ar" or "en" = the language the user wrote in\n'
        "  search_query: short ENGLISH description of what the user wants to see or do "
        '(translate from Arabic if needed), "" if they gave no preference\n'
        "  interests: list of short English words (e.g. [\"museums\", \"diving\"])\n"
        f"  region: exactly one of {known_regions()} or null. Use \"Cairo\" for Cairo, Giza and the Pyramids area.\n"
        "  unsupported_region: if the user names another place in Egypt (any city, town or area not in "
        "that list, e.g. Port Said, Ismailia, Fayoum, Dahab), put its usual ENGLISH name here and set region "
        "to null; otherwise null\n"
        "  days: whole number of days, or null. \"a day trip\", \"رحلة يوم\" and \"يوم\" on its own mean 1\n"
        '  budget: "economy", "moderate", "luxury", or null if not stated\n'
        '  travelers: "solo", "couple", "family", "group", whole number, or null if not stated\n'
        "  travel_date: a weekday name or YYYY-MM-DD, only if the user gave one, else null\n"
        '  visitor_type: "egyptian" or "foreigner", only if the user said so, else null\n'
        "Never guess a value the user did not give. Use null instead.\n"
        f"Today's date is {date.today().isoformat()} (use it to turn 'next Friday' into a date)."
    )


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _canonical_region(value: Any) -> Optional[str]:
    if not value:
        return None
    key = str(value).strip().lower()
    if key in ("cairo", "greater cairo"):
        return "Cairo"
    for region in known_regions():
        if region.lower() == key:
            return region
    return None


def normalize_intent(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and check the LLM's JSON. Never raises; bad fields become None."""
    language = "ar" if str(raw.get("language", "")).lower().startswith("ar") else "en"
    task = "plan_trip" if raw.get("task") == "plan_trip" else "other"

    try:
        days: Optional[int] = int(raw.get("days"))
    except (TypeError, ValueError):
        days = None
    if days is not None and not 1 <= days <= 14:
        days = None

    region = _canonical_region(raw.get("region"))
    unsupported = None
    if region is None:
        named = raw.get("unsupported_region") or raw.get("region")
        unsupported = str(named).strip() if named else None

    interests = raw.get("interests")
    interests = [str(i).strip() for i in interests if str(i).strip()] if isinstance(interests, list) else []

    travel_date = raw.get("travel_date")
    travel_date = str(travel_date).strip() if travel_date and resolve_day(travel_date) else None

    visitor = raw.get("visitor_type")
    visitor = resolve_visitor_type(visitor) if visitor else None

    raw_budget = str(raw.get("budget") or "").strip().lower()
    budget = None
    if any(w in raw_budget for w in ("econ", "budget", "cheap", "اقتصاد", "رخيص", "محدود")):
        budget = "economy"
    elif any(w in raw_budget for w in ("moderat", "medium", "standard", "mid", "متوسط", "عادي")):
        budget = "moderate"
    elif any(w in raw_budget for w in ("lux", "vip", "deluxe", "5 star", "فاخر", "راقي", "٥ نجوم")):
        budget = "luxury"

    raw_trav = str(raw.get("travelers") or raw.get("people") or "").strip().lower()
    travelers = None
    if any(w in raw_trav for w in ("solo", "single", "alone", "واحد", "لوحدي", "مفرد")):
        travelers = "solo"
    elif any(w in raw_trav for w in ("couple", "two", "2", "wife", "husband", "زوج", "شخصين", "٢ أفراد", "2 أفراد")):
        travelers = "couple"
    elif any(w in raw_trav for w in ("fam", "kid", "child", "عائل", "مع أولادي", "مع الأسرة")):
        travelers = "family"
    elif any(w in raw_trav for w in ("group", "friend", "مجموع", "أصدقاء", "اصدقاء", "صحاب", "أصحاب", "اصحاب", "شلة")):
        travelers = "group"
    elif raw_trav.isdigit():
        travelers = int(raw_trav)

    query = str(raw.get("search_query") or "").strip()
    if not query:
        query = " ".join(interests) if interests else (
            f"top attractions in {region}" if region else "top attractions in Egypt")

    missing: List[str] = []
    if task == "plan_trip":
        if days is None:
            missing.append("days")
        if region is None and unsupported is None:
            missing.append("region")

    return {
        "task": task, "language": language, "search_query": query, "interests": interests,
        "region": region, "unsupported_region": unsupported, "days": days,
        "budget": budget, "travelers": travelers,
        "travel_date": travel_date, "visitor_type": visitor, "missing": missing,
    }


def extract_intent(message: str, llm: LLMFn) -> Dict[str, Any]:
    """Returns {"ok": True, "intent": {...}} or {"ok": False, "error": "..."}."""
    if not isinstance(message, str) or not message.strip():
        return {"ok": False, "error": "message must be a non-empty string"}
    reply = llm(message.strip(), system=_system_prompt(), json_mode=True)
    if not reply.get("ok"):
        return {"ok": False, "error": reply.get("error", "LLM call failed")}
    raw = _parse_json(reply["text"])
    if raw is None:
        return {"ok": False, "error": "The model did not return valid JSON"}
    return {"ok": True, "intent": normalize_intent(raw)}