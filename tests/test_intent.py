import json

from agents.intent import extract_intent, normalize_intent


def fake_llm(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda prompt, system=None, json_mode=False: {"ok": True, "text": text}


GOOD = {"task": "plan_trip", "language": "en", "search_query": "ancient temples", "interests": ["temples"],
        "region": "Luxor", "unsupported_region": None, "days": 2, "travel_date": "Friday",
        "visitor_type": "tourist"}


def test_good_json_is_normalized():
    r = extract_intent("2 days in Luxor", fake_llm(GOOD))
    i = r["intent"]
    assert r["ok"] and i["region"] == "Luxor" and i["days"] == 2 and i["missing"] == []
    assert i["visitor_type"] == "foreigner" and i["travel_date"] == "Friday"


def test_arabic_message_keeps_language_and_english_query():
    raw = {**GOOD, "language": "ar", "search_query": "pyramids", "region": "Giza"}
    i = extract_intent("أريد زيارة الأهرامات", fake_llm(raw))["intent"]
    assert i["language"] == "ar" and i["search_query"] == "pyramids"


def test_code_fences_are_stripped():
    r = extract_intent("x", fake_llm("```json\n" + json.dumps(GOOD) + "\n```"))
    assert r["ok"]


def test_invalid_json_and_llm_failure_become_errors():
    assert extract_intent("x", fake_llm("not json"))["ok"] is False
    assert extract_intent("x", lambda *a, **k: {"ok": False, "error": "quota"})["error"] == "quota"
    assert extract_intent("   ", fake_llm(GOOD))["ok"] is False


def test_days_out_of_range_is_missing():
    i = normalize_intent({**GOOD, "days": 40})
    assert i["days"] is None and "days" in i["missing"]
    assert "days" in normalize_intent({**GOOD, "days": "many"})["missing"]


def test_missing_region_and_days_are_decided_in_code():
    i = normalize_intent({"task": "plan_trip", "language": "en", "region": None, "days": None})
    assert i["missing"] == ["days", "region"]


def test_unknown_region_is_flagged_not_guessed():
    i = normalize_intent({**GOOD, "region": "Dahab"})
    assert i["region"] is None and i["unsupported_region"] == "Dahab" and "region" not in i["missing"]


def test_cairo_aliases_and_garbage_date():
    assert normalize_intent({**GOOD, "region": "Greater Cairo"})["region"] == "Cairo"
    assert normalize_intent({**GOOD, "travel_date": "next monkey"})["travel_date"] is None


def test_non_trip_task():
    i = normalize_intent({"task": "chat", "language": "en"})
    assert i["task"] == "other" and i["missing"] == []


def test_budget_and_travelers_normalized():
    i1 = normalize_intent({**GOOD, "budget": "economy", "travelers": "solo"})
    assert i1["budget"] == "economy" and i1["travelers"] == "solo"

    i2 = normalize_intent({**GOOD, "budget": "فاخر", "travelers": "زوجان"})
    assert i2["budget"] == "luxury" and i2["travelers"] == "couple"

    i3 = normalize_intent({**GOOD, "budget": "mid-range", "travelers": "family of 4"})
    assert i3["budget"] == "moderate" and i3["travelers"] == "family"