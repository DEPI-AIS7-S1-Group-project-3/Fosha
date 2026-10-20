"""Milestone 5: planner pipeline with a fake llm and fake retrieval."""
import json

from agents.planner import plan_trip, reply_is_faithful, render_plain

BASE = {"task": "plan_trip", "language": "en", "search_query": "temples", "interests": [],
        "region": "Luxor", "unsupported_region": None, "days": 1, "travel_date": "Monday",
        "visitor_type": None}


def make_llm(intent, reply_fn=lambda prompt: prompt):
    """json_mode=True -> intent JSON; json_mode=False -> reply (default: echo the prompt, which holds all facts)."""
    def llm(prompt, system=None, json_mode=False):
        if json_mode:
            return {"ok": True, "text": json.dumps(intent)}
        return {"ok": True, "text": reply_fn(prompt)}
    return llm


def fake_search(query, region=None, category=None, max_duration=None, top_k=5):
    return [{"metadata": {"id": i}, "relevance_score": 0.8 + i / 100, "content": ""} for i in (9, 10, 11)]


def test_happy_path_uses_llm_reply_when_faithful():
    r = plan_trip("1 day in Luxor", make_llm(BASE), fake_search)
    assert r["ok"] and r["status"] == "planned" and r["used_fallback"] is False
    assert r["itinerary"]["days"][0]["stops"]


def test_unfaithful_reply_falls_back_to_plain_text_with_real_times():
    r = plan_trip("1 day in Luxor", make_llm(BASE, lambda p: "Enjoy Egypt!"), fake_search)
    first = r["itinerary"]["days"][0]["stops"][0]
    assert r["used_fallback"] is True and first["start"] in r["reply"]


def test_llm_failure_in_wording_step_falls_back():
    def llm(prompt, system=None, json_mode=False):
        return {"ok": True, "text": json.dumps(BASE)} if json_mode else {"ok": False, "error": "down"}
    r = plan_trip("1 day in Luxor", llm, fake_search)
    assert r["status"] == "planned" and r["used_fallback"] is True


def test_missing_days_asks_in_user_language():
    en = plan_trip("Luxor trip", make_llm({**BASE, "days": None}), fake_search)
    ar = plan_trip("رحلة", make_llm({**BASE, "days": None, "language": "ar"}), fake_search)
    assert en["status"] == "needs_clarification" and "How many days" in en["reply"]
    assert ar["language"] == "ar" and "كم" in ar["reply"]


def test_unsupported_region_and_out_of_scope():
    r = plan_trip("Dahab", make_llm({**BASE, "region": None, "unsupported_region": "Dahab"}), fake_search)
    assert r["status"] == "unsupported_region" and "Dahab" in r["reply"]
    assert plan_trip("hi", make_llm({"task": "other", "language": "en"}), fake_search)["status"] == "out_of_scope"


def test_no_results():
    r = plan_trip("x", make_llm(BASE), lambda **k: [])
    assert r["status"] == "no_results"


def test_retrieval_failure_is_an_error():
    def broken(**k):
        raise RuntimeError("db missing")
    assert plan_trip("x", make_llm(BASE), broken)["ok"] is False


def test_intent_failure_is_an_error():
    assert plan_trip("x", lambda *a, **k: {"ok": False, "error": "quota"}, fake_search)["ok"] is False


def test_prices_only_when_visitor_type_known():
    seen = {}
    def spy(prompt):
        seen["p"] = prompt
        return prompt
    plan_trip("x", make_llm(BASE, spy), fake_search)
    assert "ticket_price_egp" not in seen["p"]
    plan_trip("x", make_llm({**BASE, "visitor_type": "foreigner"}, spy), fake_search)
    assert "ticket_price_egp" in seen["p"]


def test_guard_rejects_missing_time_and_missing_price_and_accepts_arabic_digits():
    payload = {"days": [{"day": 1, "weekday": None, "area": "X", "warnings": [], "notes": [], "stops": [
        {"name": "A", "start": "09:00", "end": "12:00", "travel_from_previous_min": None,
         "hours_confidence": "listed", "ticket_price_egp": 550.0}]}], "not_included": [], "warnings": []}
    assert reply_is_faithful("09:00 to 12:00, 550 EGP", payload)
    assert reply_is_faithful("٠٩:٠٠ إلى ١٢:٠٠ و ٥٥٠ جنيه", payload)
    assert not reply_is_faithful("09:00 to 12:00", payload)           # price dropped
    assert not reply_is_faithful("09:00 to 13:00, 550", payload)      # time changed
    assert "09:00-12:00" in render_plain(payload)


def far_search(query, region=None, category=None, max_duration=None, top_k=5):
    # every Luxor place, all "weak" matches (distance above the cutoff)
    return [{"metadata": {"id": i}, "relevance_score": 1.5, "content": ""} for i in (9, 10, 11, 12, 13, 14)]


def test_weak_matches_still_fill_the_days_and_are_spread_out():
    intent = {**BASE, "days": 3, "travel_date": None}
    r = plan_trip("3 days in Luxor", make_llm(intent), far_search)
    days = r["itinerary"]["days"]
    assert len(days) == 3 and all(d["stops"] for d in days)
    assert all(len(d["stops"]) <= 2 for d in days)


def test_clarification_asks_for_budget_travelers_and_suggests_places():
    intent = {**BASE, "region": None, "days": 3, "budget": None, "travelers": None}
    r = plan_trip("3 days trip", make_llm(intent), fake_search)
    assert r["status"] == "needs_clarification"
    reply = r["reply"]
    # Check that it asks for region, budget, and travelers, and suggests places for 3 days
    assert "budget" in reply.lower()
    assert "travelling" in reply.lower() or "people" in reply.lower()
    assert "luxor" in reply.lower() or "cairo" in reply.lower()


def test_multi_day_trip_includes_hotels_and_transport():
    # 3 days in Luxor: multi-day trip -> recommendations present
    intent_3d = {**BASE, "region": "Luxor", "days": 3}
    r3 = plan_trip("3 days in Luxor", make_llm(intent_3d), far_search)
    recs = r3["itinerary"].get("recommendations", {})
    assert len(recs.get("hotels", [])) > 0
    assert len(recs.get("transport", [])) > 0

    # 1 day in Luxor: single day -> recommendations empty
    intent_1d = {**BASE, "region": "Luxor", "days": 1}
    r1 = plan_trip("1 day in Luxor", make_llm(intent_1d), fake_search)
    recs1 = r1["itinerary"].get("recommendations", {})
    assert len(recs1.get("hotels", [])) == 0
    assert len(recs1.get("transport", [])) == 0