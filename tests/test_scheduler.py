"""Milestone 4: the scheduler must never break a hard constraint."""
from agents.attractions import get_attraction
from agents.hours import check_opening_hours, to_minutes
from agents.scheduler import build_itinerary
from agents.travel import calculate_travel_time


def assert_plan_valid(plan, day_start="09:00", day_end="18:00"):
    """Hard-constraint checker, independent of the scheduler's own code."""
    assert plan["ok"], plan
    for day in plan["days"]:
        prev = None
        for stop in day["stops"]:
            start, end = to_minutes(stop["start"]), to_minutes(stop["end"])
            assert to_minutes(day_start) <= start and end <= to_minutes(day_end)
            assert end - start == get_attraction(stop["attraction_id"]).duration_min
            if day["weekday"]:
                check = check_opening_hours(stop["attraction_id"], day["weekday"], stop["start"])
                assert check["open"] is True, (stop["name"], check["reason"])
            if prev:
                travel = calculate_travel_time(prev["attraction_id"], stop["attraction_id"])
                assert not travel["long_distance"]
                assert start >= to_minutes(prev["end"]) + travel["minutes"]
            prev = stop


def test_one_day_greater_cairo_friday():
    plan = build_itinerary([1, 5, 2, 3, 4], 1, "Friday")
    assert_plan_valid(plan)
    assert 1 in [s["attraction_id"] for s in plan["days"][0]["stops"]]


def test_luxor_two_days():
    plan = build_itinerary([9, 10, 11, 12, 13, 14], 2, "Monday")
    assert_plan_valid(plan)
    assert len(plan["days"]) == 2 and plan["unscheduled"] == []


def test_closed_place_is_never_scheduled():
    plan = build_itinerary([25], 1, "Friday")      # St Catherine closed Fridays
    assert plan["ok"] and plan["days"] == [] or all(not d["stops"] for d in plan["days"])
    assert [u["attraction_id"] for u in plan["unscheduled"]] == [25]


def test_evening_session_respected():
    plan = build_itinerary([2], 1, "Tuesday", "17:00", "22:00")
    assert_plan_valid(plan, "17:00", "22:00")
    assert plan["days"][0]["stops"][0]["start"] == "18:00"


def test_no_date_uses_only_always_open_places():
    plan = build_itinerary([22, 1], 1)             # 22 closed Fridays -> must be unscheduled
    assert 22 in [u["attraction_id"] for u in plan["unscheduled"]]
    assert any("No travel date" in w for w in plan["warnings"])


def test_max_stops_per_day_cap():
    plan = build_itinerary([9, 10, 11, 12, 13, 14], 1, "Monday", max_stops_per_day=2)
    assert all(len(d["stops"]) <= 2 for d in plan["days"])


def test_duplicate_ids_are_collapsed():
    plan = build_itinerary([1, 1, 1], 1, "Monday")
    assert sum(len(d["stops"]) for d in plan["days"]) == 1


def test_far_apart_places_never_share_a_day():
    plan = build_itinerary([1, 9], 1, "Monday")
    assert_plan_valid(plan)
    assert sum(len(d["stops"]) for d in plan["days"]) == 1


def test_bad_inputs_return_errors():
    assert build_itinerary([999], 1)["ok"] is False
    assert build_itinerary([1], 0)["ok"] is False
    assert build_itinerary([], 1)["ok"] is False
    assert build_itinerary([1], 1, "Someday")["ok"] is False
    assert build_itinerary([1], 1, day_start="18:00", day_end="09:00")["ok"] is False
    assert build_itinerary(["x"], 1)["ok"] is False