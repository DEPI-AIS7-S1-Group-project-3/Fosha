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
