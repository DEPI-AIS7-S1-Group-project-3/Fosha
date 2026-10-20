"""Editing the current plan from chat (the LLM is faked: it only returns the edit JSON)."""
import json

from agents.planner import plan_trip

INTENT = {"task": "plan_trip", "language": "en", "search_query": "", "interests": [], "region": "Luxor",
          "unsupported_region": None, "days": 1, "travel_date": None, "visitor_type": None}
# Luxor: 10 Luxor Temple, 12 Hatshepsut, 13 Mummification Museum, 14 Deir al-Bahari, 11 Valley of the Kings
CONTEXT = {"intent": INTENT, "days": [[12, 14]]}


def llm_returning(edit):
    def llm(prompt, system=None, json_mode=False):
        assert json_mode and "AVAILABLE" in prompt
        return {"ok": True, "text": json.dumps(edit)}
    return llm


def stops(result):
    return [s["attraction_id"] for d in result["itinerary"]["days"] for s in d["stops"]]


def test_add_after_a_stop_and_retime():
    r = plan_trip("put the mummification museum after hatshepsut", context=CONTEXT,
                  llm=llm_returning({"type": "edit", "add": [{"id": 13, "after_id": 12, "day": None}], "remove": []}))
    assert r["status"] == "planned" and r["edited"] is True
    assert stops(r) == [12, 13, 14]
    day = r["itinerary"]["days"][0]["stops"]
    assert day[0]["end"] <= day[1]["start"] and day[1]["travel_from_previous_min"] is not None
    assert "added Mummification Museum after Hatshepsut Temple" in r["reply"]


def test_remove_a_stop():
    r = plan_trip("drop deir al bahari", context=CONTEXT,
                  llm=llm_returning({"type": "edit", "add": [], "remove": [14]}))
    assert stops(r) == [12] and "removed Deir al-Bahari" in r["reply"]


def test_ids_outside_the_lists_are_ignored():
    r = plan_trip("add the pyramids", context=CONTEXT,
                  llm=llm_returning({"type": "edit", "add": [{"id": 5, "after_id": None}], "remove": [999]}))
    assert r["status"] == "edit_not_applied"  # Giza is not in this plan's area: nothing invented


def test_place_that_no_longer_fits_is_reported_not_squeezed_in():
    long_day = {"intent": INTENT, "days": [[11, 12, 14]]}
    r = plan_trip("add karnak after the valley", context=long_day,
                  llm=llm_returning({"type": "edit", "add": [{"id": 9, "after_id": 11}], "remove": []}))
    assert 9 in [d["attraction_id"] for d in r["itinerary"]["unscheduled"]] or 9 in stops(r)
    if 9 not in stops(r):
        assert "no longer fits" in r["reply"]


def test_a_new_trip_is_not_treated_as_an_edit():
    calls = []
    def llm(prompt, system=None, json_mode=False):
        calls.append(prompt)
        if "AVAILABLE" in prompt:
            return {"ok": True, "text": json.dumps({"type": "new_trip"})}
        if json_mode:
            return {"ok": True, "text": json.dumps({**INTENT, "region": "Aswan", "days": 2})}
        return {"ok": True, "text": "Aswan it is!"}
    fake_search = lambda **k: [{"metadata": {"id": i}, "relevance_score": 0.5, "content": ""} for i in (15, 16)]
    r = plan_trip("actually 2 days in Aswan", llm=llm, search_fn=fake_search, context=CONTEXT)
    assert r["status"] == "planned" and not r.get("edited") and set(stops(r)) <= {15, 16}


def llm_edit_then_intent(edit, intent):
    """The edit check sees `edit`; if it falls through to normal planning, intent extraction sees `intent`."""
    def llm(prompt, system=None, json_mode=False):
        if "AVAILABLE" in prompt:
            return {"ok": True, "text": json.dumps(edit)}
        if json_mode:
            return {"ok": True, "text": json.dumps(intent)}
        return {"ok": True, "text": "ok"}
    return llm


def test_a_new_request_is_not_an_edit_even_if_the_model_says_so():
    # Real case: "عايزة اطلع يوم مع صحابي" with a plan open; the model answered edit + days 3.
    new_trip = {**INTENT, "region": None, "days": 1, "language": "ar", "travelers": "group"}
    r = plan_trip("عايزة اطلع يوم مع صحابي", context=CONTEXT,
                  llm=llm_edit_then_intent({"type": "edit", "add": [], "remove": [], "days": 3}, new_trip))
    assert not r.get("edited") and r["status"] == "needs_clarification"   # asks where to, like a new trip
    r = plan_trip("عايزة اطلع يوم", context=CONTEXT,
                  llm=llm_edit_then_intent({"type": "edit", "add": [], "remove": [], "days": None}, new_trip))
    assert r["status"] != "edit_not_applied" and not r.get("edited")


def test_days_change_needs_the_number_and_a_change_word():
    lux = {"intent": INTENT, "days": [[12, 14], [10]]}
    r = plan_trip("خليها ٣ أيام", context=lux, llm=llm_returning({"type": "edit", "add": [], "remove": [], "days": 3}))
    assert r["edited"] and len(r["itinerary"]["days"]) == 3
    assert all(d["stops"] for d in r["itinerary"]["days"])          # new days filled from nearby places
    assert "٣ أيام" in r["reply"]


def test_never_leaves_empty_days_when_places_run_out():
    siwa = {"intent": {**INTENT, "region": "Matrouh"}, "days": [[28]]}   # Matrouh has 2 curated places
    r = plan_trip("make it 5 days instead", context=siwa,
                  llm=llm_returning({"type": "edit", "add": [], "remove": [], "days": 5}))
    assert r["edited"] and all(d["stops"] for d in r["itinerary"]["days"])
    assert len(r["itinerary"]["days"]) < 5 and "only enough places nearby" in r["reply"]


def test_removal_the_user_never_asked_for_is_ignored():
    r = plan_trip("add the mummification museum", context=CONTEXT,
                  llm=llm_returning({"type": "edit", "add": [{"id": 13}], "remove": [12]}))
    assert 12 in stops(r)                                              # Hatshepsut was not removed
    assert 13 in stops(r) or "Mummification Museum no longer fits" in r["reply"]
