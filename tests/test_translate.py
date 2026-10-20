"""Arabic copies of the plan's English text (the model is faked)."""
import json

from agents.translate import keeps_facts, localize_itinerary, to_arabic


def fake_llm(mapping, calls=None):
    def llm(prompt, system=None, json_mode=False):
        if calls is not None:
            calls.append(prompt)
        keyed = json.loads(prompt)
        return {"ok": True, "text": json.dumps({k: mapping.get(v, "") for k, v in keyed.items()}, ensure_ascii=False)}
    return llm


def test_facts_must_survive_translation():
    assert keeps_facts("Closed between 14:00 and 17:00.", "مغلق بين ١٤:٠٠ و١٧:٠٠.")
    assert not keeps_facts("Closed between 14:00 and 17:00.", "مغلق بعد الظهر.")
    assert keeps_facts("Ticket 550 EGP", "التذكرة 550 جنيه")


def test_translations_are_cached_and_bad_ones_dropped(tmp_path):
    cache = tmp_path / "t.json"
    mapping = {"West Bank of the Nile.": "البر الغربي للنيل.",
               "Closed between 14:00 and 17:00.": "مغلق وقت الظهر."}   # loses the times
    calls = []
    out = to_arabic(["West Bank of the Nile.", "Closed between 14:00 and 17:00.", "", "مكتوب بالعربي"],
                    fake_llm(mapping, calls), cache_path=cache)
    assert out == {"West Bank of the Nile.": "البر الغربي للنيل."}   # the fact-changing one is kept English
    to_arabic(["West Bank of the Nile."], fake_llm(mapping, calls), cache_path=cache)
    assert len(calls) == 1   # second time from the cache


def test_localize_itinerary_adds_arabic_copies(tmp_path):
    itinerary = {
        "days": [{"warnings": ["Check before you go."], "notes": [],
                  "stops": [{"description": "A big temple.", "hours_note": "", "place_note": "West Bank."}]}],
        "warnings": ["Travel times are estimates."], "unscheduled": [{"reason": "No room left."}],
    }
    mapping = {"Check before you go.": "اتأكد قبل ما تروح.", "A big temple.": "معبد كبير.",
               "West Bank.": "البر الغربي.", "Travel times are estimates.": "أوقات التنقل تقديرية.",
               "No room left.": "مفيش مكان."}
    localize_itinerary(itinerary, fake_llm(mapping), cache_path=tmp_path / "t.json")
    stop = itinerary["days"][0]["stops"][0]
    assert stop["description_ar"] == "معبد كبير." and stop["place_note_ar"] == "البر الغربي."
    assert "hours_note_ar" not in stop   # empty text: nothing to translate
    assert itinerary["days"][0]["warnings_ar"] == ["اتأكد قبل ما تروح."]
    assert itinerary["warnings_ar"] == ["أوقات التنقل تقديرية."] and itinerary["unscheduled"][0]["reason_ar"] == "مفيش مكان."
    assert stop["description"] == "A big temple."   # the English stays for the English UI
