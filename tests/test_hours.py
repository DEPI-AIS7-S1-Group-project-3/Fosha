"""Milestone 2: structured opening hours (the hard rule)."""
from agents.hours import check_opening_hours, resolve_day, validate_hours


def test_hours_file_is_consistent():
    assert validate_hours() == []


def test_resolve_day():
    assert resolve_day("Friday") == "fri"
    assert resolve_day("Thurs") == "thu"
    assert resolve_day("2026-10-23") == "fri"   # 23 Oct 2026 is a Friday
    assert resolve_day("someday") is None


def test_visit_inside_window():
    assert check_opening_hours(1, "Friday", "09:00", 120)["open"] is True


def test_visit_running_past_closing_is_rejected():
    r = check_opening_hours(1, "Friday", "15:30", 120)
    assert r["open"] is False and "09:00-17:00" in r["reason"]


def test_visit_ending_exactly_at_close_is_ok():
    assert check_opening_hours(1, "Monday", "15:00", 120)["open"] is True


def test_split_hours_midday_closure():
    # Mummification Museum: 09-14 and 17-21
    assert check_opening_hours(13, "Monday", "13:00", 60)["open"] is True
    assert check_opening_hours(13, "Monday", "13:30", 60)["open"] is False
    assert check_opening_hours(13, "Monday", "17:00", 60)["open"] is True


def test_weekday_override_adds_evening_session():
    assert check_opening_hours(15, "Thursday", "18:00", 90)["open"] is True
    assert check_opening_hours(15, "Monday", "18:00", 90)["open"] is False


def test_closed_all_day_and_by_iso_date():
    assert check_opening_hours(25, "Friday", "09:00")["open"] is False
    assert check_opening_hours(25, "2026-10-23", "09:00")["open"] is False  # a Friday
    assert check_opening_hours(25, "Monday", "09:00", 150)["open"] is True
    assert check_opening_hours(25, "Monday", "09:00", 180)["open"] is False  # past 11:30


def test_all_day_place():
    assert check_opening_hours(28, "Sunday", "23:00", 60)["open"] is True


def test_uncertain_hours_are_flagged():
    assert check_opening_hours(5, "Monday", "09:00", 60)["confidence"] == "uncertain"


def test_bad_input_returns_error_not_exception():
    assert check_opening_hours(1, "someday", "09:00")["ok"] is False
    assert check_opening_hours(1, "Monday", "9am")["ok"] is False
    assert check_opening_hours(999, "Monday", "09:00")["ok"] is False
    assert check_opening_hours("x", "Monday", "09:00")["ok"] is False
    assert check_opening_hours(1, "Monday", "09:00", "long")["ok"] is False