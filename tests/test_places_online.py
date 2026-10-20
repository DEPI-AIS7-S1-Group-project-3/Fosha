"""Places outside the curated dataset, looked up online (all network calls are faked)."""
import json

from agents import places_online as po
from agents.hours import get_windows
from agents.planner import plan_trip
from agents.pricing import check_ticket_price

WIKITEXT = """==See==
* {{see
| name=Lighthouse of Port Said | lat=31.264098 | long=32.313407
| content=One of the icons of the city, built in [[1869]] next to the [[Suez Canal|canal]].
}}
* {{see | name=Port Said Military Museum | wikidata=Q123 | hours=9AM-2PM | price=Entry 5 EGP, camera 2 EGP
| content=Inaugurated in 1964.}}
* {{see | name=El-Abbasy Mosque | content=Built in 1904 by Abbas II.}}
* {{see | name=Far Away Fort | lat=29.0 | long=31.0 | content=Wrong coordinates, 250 km away.}}
"""


def fake_fetch(calls=None):
    def fetch(url, params):
        if calls is not None:
            calls.append((url, params.get("action") or params.get("q")))
        if url == po.NOMINATIM:
            if "nowhere" in params["q"]:
                return []
            return [{"name": "Port Said", "lat": "31.2632", "lon": "32.3055", "display_name": "Port Said, Egypt",
                     "namedetails": {"name:ar": "بورسعيد", "name:en": "Port Said"}, "extratags": {}}]
        if url == po.WIKIVOYAGE and params.get("action") == "parse":
            return {"parse": {"title": "Port Said", "wikitext": WIKITEXT}}
        if url == po.WIKIDATA:
            return {"entities": {"Q123": {"labels": {"ar": {"value": "متحف بورسعيد الحربي"}},
                                          "claims": {"P625": [{"mainsnak": {"datavalue": {"value": {
                                              "latitude": 31.262, "longitude": 32.302}}}}]}}}}
        return {}
    return fetch


def test_wikitext_parsing_and_cleaning():
    listings = po.parse_listings(WIKITEXT)
    assert [l["name"] for l in listings][:3] == ["Lighthouse of Port Said", "Port Said Military Museum",
                                                 "El-Abbasy Mosque"]
    assert listings[0]["content"] == "One of the icons of the city, built in 1869 next to the canal."
    assert listings[1]["wikidata"] == "Q123"


def test_field_parsers():
    assert po.parse_hours("9AM-2PM") == ["09:00", "14:00"]
    assert po.parse_hours("daily 08:30–16:00") == ["08:30", "16:00"]
    assert po.parse_hours("9-5") == ["09:00", "17:00"]
    assert po.parse_hours("ask locally") is None
    assert po.parse_price("Entry 5 EGP, camera 2 EGP") == 5.0
    assert po.parse_price("LE 60") == 60.0 and po.parse_price("free") == 0.0
    assert po.parse_price("") is None
    assert po.categorise("El-Abbasy Mosque", "") == "Religious Site"
    assert po.categorise("Port Said Military Museum", "") == "Museum"
    assert po.categorise("Corniche", "8-km walkway") == "Park / Promenade"


def test_find_places_uses_sources_and_cache(tmp_path):
    calls = []
    cache = tmp_path / "cache.json"
    found = po.find_places("بورسعيد", fetch=fake_fetch(calls), cache_path=cache)
    assert found["ok"] and found["city"]["name"] == "Port Said"
    names = [p["name"] for p in found["places"]]
    assert "Far Away Fort" not in names  # 250 km from the town: dropped
    museum = next(p for p in found["places"] if p["name"] == "Port Said Military Museum")
    assert museum["name_ar"] == "متحف بورسعيد الحربي" and museum["lat"] == 31.262
    assert museum["window"] == ["09:00", "14:00"] and museum["price_egp"] == 5.0
    mosque = next(p for p in found["places"] if p["name"] == "El-Abbasy Mosque")
    assert mosque["approximate_location"] and mosque["price_egp"] is None
    n = len(calls)
    po.find_places("  بورسعيد ", fetch=fake_fetch(calls), cache_path=cache)
    assert len(calls) == n  # second lookup served from the disk cache
    assert "Port Said" in json.loads(cache.read_text(encoding="utf-8"))["بورسعيد"]["city"]["name"]


def test_not_found_and_offline(tmp_path):
    assert po.find_places("nowhere town", fetch=fake_fetch(), cache_path=tmp_path / "c.json")["reason"] == "not_found"

    def broken(url, params):
        raise OSError("network down")
    result = po.find_places("Port Said", fetch=broken, cache_path=tmp_path / "c2.json")
    assert result == {"ok": False, "reason": "offline"}
    assert not (tmp_path / "c2.json").exists()  # failures are not cached


def test_registered_places_follow_the_same_rules(tmp_path):
    found = po.find_places("Port Said", fetch=fake_fetch(), cache_path=tmp_path / "c.json")
    ids = po.register_places(found["places"])
    museum_id = next(i for i, p in zip(ids, found["places"]) if p["name"] == "Port Said Military Museum")
    assert get_windows(museum_id, "mon") == [(9 * 60, 14 * 60)]
    mosque_id = next(i for i, p in zip(ids, found["places"]) if p["name"] == "El-Abbasy Mosque")
    assert check_ticket_price(mosque_id, "foreigner")["ok"] is False  # no price listed: never guessed
    assert po.arabic_name(museum_id) == "متحف بورسعيد الحربي" and po.arabic_area("Port Said") == "بورسعيد"


def _llm_for(intent):
    def llm(prompt, system=None, json_mode=False):
        if json_mode:
            return {"ok": True, "text": json.dumps(intent, ensure_ascii=False)}
        return {"ok": False, "error": "use the plain fallback"}
    return llm


BASE = {"task": "plan_trip", "language": "ar", "search_query": "", "interests": [], "region": None,
        "unsupported_region": "Port Said", "days": 1, "travel_date": None, "visitor_type": None,
        "budget": None, "travelers": "group"}


def test_planner_plans_a_place_outside_the_dataset(tmp_path):
    places = lambda name: po.find_places(name, fetch=fake_fetch(), cache_path=tmp_path / "c.json")
    r = plan_trip("رحلة يوم في بورسعيد مع صحابي", _llm_for(BASE), places_fn=places)
    assert r["status"] == "planned"
    stops = r["itinerary"]["days"][0]["stops"]
    assert stops and all(po.is_dynamic(s["attraction_id"]) for s in stops)
    assert r["itinerary"]["days"][0]["area"] == "Port Said"


def test_planner_asks_days_and_names_the_place(tmp_path):
    places = lambda name: po.find_places(name, fetch=fake_fetch(), cache_path=tmp_path / "c.json")
    r = plan_trip("بورسعيد", _llm_for({**BASE, "days": None}), places_fn=places)
    assert r["status"] == "needs_clarification" and "بورسعيد" in r["reply"] and "كام يوم" in r["reply"]


def test_planner_explains_when_a_place_cannot_be_found():
    r = plan_trip("x", _llm_for({**BASE, "unsupported_region": "Atlantis"}),
                  places_fn=lambda name: {"ok": False, "reason": "not_found"})
    assert r["status"] == "unsupported_region" and "Atlantis" in r["reply"] and "مصر" in r["reply"]
    assert "Alexandria, Aswan" not in r["reply"]  # no English list dumped into an Arabic reply
