"""message -> intent -> retrieval -> scheduler -> reply.

LLM does: understanding (intent.py) and wording (below).
Plain Python does: every fact and every hard constraint (hours, travel, prices).
The wording step is guarded: if the LLM reply drops a scheduled time or a price,
we throw it away and show a plain deterministic rendering instead.

Run a manual check:  uv run python -m agents.planner "3 days in Luxor, I love temples"
"""
import json
import math
import sys
from typing import Any, Callable, Dict, List, Optional

from agents.intent import extract_intent, known_regions
from agents.llm import generate
from agents.pricing import check_ticket_price
from agents.recommendations import format_clarification_message, get_recommendations, regions_for_days
from agents.retrieval_adapter import search_attractions
from agents.scheduler import build_itinerary

LLMFn = Callable[..., Dict[str, Any]]
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

MESSAGES = {
    "ask_days": {"en": "How many days do you have for the trip?",
                 "ar": "كم يومًا لديك لهذه الرحلة؟"},
    "ask_region": {"en": "Which city or area would you like to visit? Available: {regions}.",
                   "ar": "ما المدينة أو المنطقة التي تريد زيارتها؟ المتاح: {regions}."},
    "unsupported": {"en": "I don't have data for {place} yet. I can plan trips in: {regions}.",
                    "ar": "ليست لدي بيانات عن {place} حاليًا. يمكنني تخطيط رحلات في: {regions}."},
    "other": {"en": "For now I can plan itineraries in Egypt. Try: \"2 days in Luxor, I love temples\".",
              "ar": "حاليًا أستطيع تخطيط برامج رحلات في مصر. جرّب: \"يومان في الأقصر وأحب المعابد\"."},
    "no_results": {"en": "I couldn't find matching places. Try different interests or another area.",
                   "ar": "لم أجد أماكن مطابقة. جرّب اهتمامات مختلفة أو منطقة أخرى."},
}


def _say(key: str, lang: str, **fields: str) -> str:
    return MESSAGES[key][lang].format(**fields)


def _payload(itinerary: Dict[str, Any], visitor_type: Optional[str]) -> Dict[str, Any]:
    days = []
    for day in itinerary["days"]:
        stops = []
        for stop in day["stops"]:
            item = {k: stop[k] for k in ("name", "start", "end", "travel_from_previous_min", "hours_confidence")}
            if visitor_type:
                price = check_ticket_price(stop["attraction_id"], visitor_type)
                if price["ok"]:
                    egp = price["price_egp"]
                    item["ticket_price_egp"] = int(egp) if float(egp).is_integer() else egp
                    if egp == 0:  # 0 may mean free OR not recorded: keep the per-stop warning
                        item["price_note"] = price["price_note"]
            stops.append(item)
        days.append({"day": day["day"], "weekday": day["weekday"], "area": day["area"],
                     "stops": stops, "warnings": day["warnings"], "notes": day["notes"]})
    result: Dict[str, Any] = {
        "days": days,
        "not_included": [{"name": u["name"], "reason": u["reason"]} for u in itinerary["unscheduled"]],
        "warnings": itinerary["warnings"],
    }
    recs = itinerary.get("recommendations") or {}
    if recs.get("hotels") or recs.get("transport"):
        # The ranking score is internal; the writer only needs the picks and their reasons.
        result["recommendations"] = {
            key: [{k: v for k, v in item.items() if k != "score"} for item in recs.get(key, [])]
            for key in ("hotels", "transport")
        }
        result["recommendations"]["based_on"] = recs.get("based_on", [])
    if visitor_type:
        result["prices_note"] = "Adult ticket prices only; they can change, so verify on the official source."
    return result


def render_plain(payload: Dict[str, Any]) -> str:
    """Deterministic fallback (English). Contains every fact the guard checks for."""
    lines: List[str] = []
    for day in payload["days"]:
        label = f"Day {day['day']} - {day['area']}" + (f" ({day['weekday'].upper()})" if day["weekday"] else "")
        lines.append(label)
        for stop in day["stops"]:
            extra = f", travel {stop['travel_from_previous_min']} min" if stop["travel_from_previous_min"] else ""
            price = f", ticket {stop['ticket_price_egp']:g} EGP" if "ticket_price_egp" in stop else ""
            lines.append(f"  {stop['start']}-{stop['end']}  {stop['name']}{extra}{price}")
        lines.extend(f"  ! {w}" for w in day["warnings"])
    lines.extend(f"Not included: {u['name']} - {u['reason']}" for u in payload["not_included"])
    lines.extend(f"Note: {w}" for w in payload["warnings"])

    recs = payload.get("recommendations") or {}
    hotels = recs.get("hotels") or []
    if hotels:
        lines.append("\nRecommended Accommodation:")
        for h in hotels:
            example = f" (e.g. {h['example']})" if h.get("example") else ""
            why = f" - why: {'; '.join(h['why'])}" if h.get("why") else ""
            lines.append(f"  - {h['area']}: {h['desc']}{example}{why}")
    transport = recs.get("transport") or []
    if transport:
        lines.append("\nTransport Options:")
        for t in transport:
            why = f" - why: {'; '.join(t['why'])}" if t.get("why") else ""
            lines.append(f"  - {t['mode']}: {t['desc']}{why}")

    return "\n".join(lines)


def reply_is_faithful(reply: str, payload: Dict[str, Any]) -> bool:
    """Hard guard: every scheduled time and every ticket price must appear in the reply."""
    text = reply.translate(_ARABIC_DIGITS).replace(",", "")
    for day in payload["days"]:
        for stop in day["stops"]:
            if stop["start"] not in text or stop["end"] not in text:
                return False
            if "ticket_price_egp" in stop and f"{stop['ticket_price_egp']:g}" not in text:
                return False
    return True


def _write_reply(payload: Dict[str, Any], language: str, llm: LLMFn) -> Dict[str, Any]:
    name = "Arabic" if language == "ar" else "English"
    prompt = (
        f"Write the itinerary below as a friendly, clear travel plan in {name}.\n"
        "Rules: use ONLY the data given. Keep every place name, time and price exactly as given "
        "(use the 24-hour HH:MM times as written). Do not add attractions, opening hours, prices or tips "
        "that are not in the data. Mention warnings and not-included places only when those lists are "
        "non-empty, and never mention field names such as not_included. Say travel times are estimates. If prices_note is present, say it once; do not repeat it per stop. "
        "If recommendations are present, offer them as suggestions picked for this traveller: for each one say "
        "briefly why it fits, using only its 'why' reasons, and name example hotels only as given in 'example'.\n\nDATA:\n" + json.dumps(payload, ensure_ascii=False, indent=1)
    )
    result = llm(prompt, system=None, json_mode=False)
    if result.get("ok") and reply_is_faithful(result["text"], payload):
        return {"reply": result["text"].strip(), "used_fallback": False}
    return {"reply": render_plain(payload), "used_fallback": True}


def plan_trip(message: str, llm: LLMFn = generate, search_fn: Optional[Callable[..., Any]] = None) -> Dict[str, Any]:
    """Returns {"ok": False, "error": ...} or {"ok": True, "status": ..., "language": ..., "reply": ...}.
    status: planned | needs_clarification | unsupported_region | out_of_scope | no_results
    """
    extracted = extract_intent(message, llm)
    if not extracted["ok"]:
        return {"ok": False, "error": extracted["error"]}
    intent = extracted["intent"]
    lang = intent["language"]
    regions = ", ".join(known_regions())

    def done(status: str, reply: str, **more: Any) -> Dict[str, Any]:
        return {"ok": True, "status": status, "language": lang, "reply": reply, "intent": intent, **more}

    if intent["task"] != "plan_trip":
        return done("out_of_scope", _say("other", lang))
    if intent["unsupported_region"]:
        return done("unsupported_region", _say("unsupported", lang, place=intent["unsupported_region"], regions=regions))
    if intent["missing"]:
        reply = format_clarification_message(
            missing=intent["missing"],
            days=intent.get("days"),
            budget=intent.get("budget"),
            travelers=intent.get("travelers"),
            language=lang,
            all_regions=regions,
        )
        return done("needs_clarification", reply, missing=intent["missing"],
                    suggested_regions=regions_for_days(intent.get("days")))

    top_k = min(12, max(6, intent["days"] * 4))
    found = search_attractions(intent["search_query"], region=intent["region"], top_k=top_k,
                              apply_cutoff=False, search_fn=search_fn)
    if not found["ok"]:
        return {"ok": False, "error": found["error"]}
    candidate_ids = [r["attraction"]["id"] for r in found["results"]]
    if not candidate_ids:
        return done("no_results", _say("no_results", lang))

    # Spread places over the days instead of filling day 1 first (2-4 stops per day).
    per_day = min(4, max(2, math.ceil(len(candidate_ids) / intent["days"])))
    itinerary = build_itinerary(candidate_ids, intent["days"], first_day=intent["travel_date"],
                                max_stops_per_day=per_day)
    if not itinerary["ok"]:
        return {"ok": False, "error": itinerary["error"]}

    itinerary["recommendations"] = get_recommendations(
        intent["region"], intent["days"], lang,
        interests=intent.get("interests"), search_query=intent.get("search_query"),
        budget=intent.get("budget"), travelers=intent.get("travelers"), itinerary=itinerary,
    )

    payload = _payload(itinerary, intent["visitor_type"])
    written = _write_reply(payload, lang, llm)
    return done("planned", written["reply"], itinerary=itinerary, used_fallback=written["used_fallback"])


if __name__ == "__main__":
    text = " ".join(sys.argv[1:]) or "3 days in Luxor, I love temples"
    result = plan_trip(text)
    print(result.get("reply") or result)
    if result.get("ok"):
        print(f"\n[status={result['status']} language={result['language']} fallback={result.get('used_fallback')}]")