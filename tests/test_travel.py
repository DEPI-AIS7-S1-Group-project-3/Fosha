"""Milestone 3 (travel time): estimates from coordinates."""
from agents.travel import calculate_travel_time, validate_locations


def test_locations_file_is_consistent():
    assert validate_locations() == []


def test_same_place_is_zero():
    assert calculate_travel_time(1, 1)["minutes"] == 0


def test_cairo_to_giza_is_reasonable_and_marked_estimate():
    r = calculate_travel_time(1, 5)
    assert r["ok"] and r["estimate"] is True
    assert 25 <= r["minutes"] <= 75 and r["long_distance"] is False


def test_symmetric():
    assert calculate_travel_time(1, 5)["minutes"] == calculate_travel_time(5, 1)["minutes"]


def test_far_apart_is_long_distance():
    assert calculate_travel_time(17, 15)["long_distance"] is True   # Abu Simbel <-> Aswan
    assert calculate_travel_time(1, 9)["long_distance"] is True     # Cairo <-> Luxor


def test_bad_ids():
    assert calculate_travel_time(1, 999)["ok"] is False
    assert calculate_travel_time("x", 1)["ok"] is False