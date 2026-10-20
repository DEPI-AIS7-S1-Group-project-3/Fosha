"""Recommendations must change with the traveller and the plan, not just the region."""
from agents.recommendations import (get_recommendations, interest_tags, load_catalogue,
                                    traveler_types)

# Minimal itinerary shapes: only attraction ids/names are read.
LUXOR_WEST = {"days": [
    {"day": 1, "stops": [{"attraction_id": 11, "name": "Valley of the Kings"},
                         {"attraction_id": 12, "name": "Hatshepsut Temple"}]},
    {"day": 2, "stops": [{"attraction_id": 9, "name": "Karnak Temple"}]},
]}
LUXOR_EAST = {"days": [
    {"day": 1, "stops": [{"attraction_id": 9, "name": "Karnak Temple"},
                         {"attraction_id": 10, "name": "Luxor Temple"}]},
    {"day": 2, "stops": [{"attraction_id": 13, "name": "Mummification Museum"}]},
]}
CAIRO_GIZA = {"days": [
    {"day": 1, "stops": [{"attraction_id": 5, "name": "Giza Pyramids / Great Pyramid"},
                         {"attraction_id": 6, "name": "Saqqara"}]},
    {"day": 2, "stops": [{"attraction_id": 1, "name": "The Egyptian Museum"}]},
]}
CAIRO_AND_LUXOR = {"days": [
    {"day": 1, "area": "Greater Cairo", "stops": [{"attraction_id": 1, "name": "The Egyptian Museum"}]},
    {"day": 2, "area": "Luxor", "stops": [{"attraction_id": 9, "name": "Karnak Temple"}]},
]}


def modes(recs):
    return [t["mode"] for t in recs["transport"]]


def test_single_day_or_no_region_gives_nothing():
    assert get_recommendations("Luxor", 1)["hotels"] == []
    assert get_recommendations(None, 3)["hotels"] == []


def test_catalogue_is_consistent():
    cat = load_catalogue()
    for item in cat["hotels"] + cat["transport"]:
        assert set(item["budgets"]) <= {"economy", "moderate", "luxury"}, item["id"]
        assert set(item.get("travelers", [])) <= {"solo", "couple", "family", "group"}, item["id"]
    for h in cat["hotels"]:
        assert {"en", "ar"} <= h["name"].keys() and {"en", "ar"} <= h["desc"].keys()


def test_interest_and_traveler_parsing():
    assert {"history"} <= interest_tags(["temples"])
    assert {"diving", "beach"} <= interest_tags(["snorkelling", "beach"])
    assert {"nile", "romance"} <= interest_tags(["رحلة رومانسية للنيل"])
    assert traveler_types(2) == {"couple"} and traveler_types("family") == {"family"}
    assert traveler_types(None) == set()


def test_budget_changes_the_example_hotels():
    lux = get_recommendations("Luxor", 3, budget="luxury", itinerary=LUXOR_EAST)
    eco = get_recommendations("Luxor", 3, budget="economy", itinerary=LUXOR_EAST)
    assert [h["example"] for h in lux["hotels"]] != [h["example"] for h in eco["hotels"]]
    assert any("budget" in (h["example"] or "") or "guesthouse" in (h["example"] or "") for h in eco["hotels"])


def test_budget_filters_transport():
    eco = get_recommendations("Luxor", 3, budget="economy", itinerary=LUXOR_WEST)
    lux = get_recommendations("Luxor", 3, budget="luxury", itinerary=LUXOR_WEST)
    assert "Public Nile ferry" in modes(eco) and "Sunrise hot-air balloon" not in modes(eco)
    assert "Public Nile ferry" not in modes(lux)


def test_plan_decides_place_specific_transport():
    west = get_recommendations("Luxor", 3, itinerary=LUXOR_WEST)
    east = get_recommendations("Luxor", 3, itinerary=LUXOR_EAST)
    assert "West Bank morning taxi" in modes(west)
    assert "West Bank morning taxi" not in modes(east)
    taxi = next(t for t in west["transport"] if t["mode"] == "West Bank morning taxi")
    assert any("Valley of the Kings" in w for w in taxi["why"])


def test_hotel_nearest_to_the_plan_ranks_first():
    west = get_recommendations("Luxor", 3, itinerary={"days": [
        {"day": 1, "stops": [{"attraction_id": 11, "name": "Valley of the Kings"},
                             {"attraction_id": 12, "name": "Hatshepsut Temple"},
                             {"attraction_id": 14, "name": "Deir al-Bahari"}]}]})
    assert west["hotels"][0]["area"].startswith("West Bank")
    assert west["hotels"][0]["why"][0].startswith("Closest to")


def test_interests_and_travelers_reorder_and_explain():
    beach = get_recommendations("Alexandria", 2, interests=["beach"], travelers="couple")
    culture = get_recommendations("Alexandria", 2, interests=["museums", "history"], travelers="solo")
    assert beach["hotels"][0]["area"] == "Corniche & Stanley Bay"
    assert culture["hotels"][0]["area"] == "Raml Station & Mansheya"
    assert any("the beach" in w for w in beach["hotels"][0]["why"])
    assert "couples" in beach["based_on"]


def test_cairo_day_trip_driver_only_with_giza_sites():
    with_giza = get_recommendations("Cairo", 2, budget="moderate", itinerary=CAIRO_GIZA)
    assert "Private car with driver" in modes(with_giza)
    museums_only = get_recommendations("Cairo", 2, budget="moderate", itinerary={"days": [
        {"day": 1, "stops": [{"attraction_id": 1, "name": "The Egyptian Museum"}]}]})
    assert "Private car with driver" not in modes(museums_only)


def test_multi_city_trip_covers_each_city_and_links_them():
    recs = get_recommendations("Cairo", 2, itinerary=CAIRO_AND_LUXOR)
    assert {h["region"] for h in recs["hotels"]} == {"Cairo", "Luxor"}
    assert "Cairo to Luxor / Aswan" in modes(recs)


def test_arabic_output():
    recs = get_recommendations("Aswan", 3, "ar", budget="luxury", travelers="couple",
                               itinerary={"days": [{"day": 1, "stops": [{"attraction_id": 16, "name": "Philae Temple"}]}]})
    assert recs["hotels"][0]["area"] in ("كورنيش أسوان", "جزيرة إلفنتين وغرب أسوان")
    assert any("الأزواج" in w for w in recs["hotels"][0]["why"])
    assert "ميزانية فاخرة" in recs["based_on"]


def test_one_day_clarification_respects_what_was_said():
    from agents.recommendations import format_clarification_message, regions_for_days
    ar = format_clarification_message(["region"], days=1, travelers="group", language="ar")
    assert "يوم واحد" in ar and "صحابك" in ar
    assert "الميزانية" not in ar and "مين مسافر" not in ar  # no hotels for a day trip, so don't ask
    assert "أسوان" not in ar
    en = format_clarification_message(["region"], days=1, language="en")
    assert "budget" not in en.lower() and "Aswan" not in en
    assert regions_for_days(1) == ["Cairo", "Alexandria"]
    assert "Red Sea" in regions_for_days(5) and len(regions_for_days(None)) == 6


def test_multi_day_clarification_offers_personalisation_once():
    from agents.recommendations import format_clarification_message
    msg = format_clarification_message(["region"], days=4, language="ar")
    assert "٤ أيام" in msg and "الميزانية" in msg
    msg = format_clarification_message(["region"], days=4, budget="luxury", travelers="couple", language="en")
    assert "budget" not in msg.lower() and "for two" in msg
