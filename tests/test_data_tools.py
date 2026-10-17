"""Milestones 1 & 3 (price): attraction lookup and ticket price. No LLM, no Chroma."""
from agents.attractions import get_attraction_details, load_attractions
from agents.pricing import check_ticket_price, resolve_visitor_type


def test_all_30_attractions_load():
    assert len(load_attractions()) == 30


def test_details_ok():
    r = get_attraction_details(1)
    assert r["ok"] and r["attraction"]["name"] == "The Egyptian Museum"


def test_details_accepts_numeric_string():
    assert get_attraction_details("5")["ok"]


def test_details_bad_input_never_raises():
    assert get_attraction_details("abc")["ok"] is False
    assert get_attraction_details(None)["ok"] is False
    assert get_attraction_details(999)["ok"] is False


def test_visitor_type_synonyms():
    assert resolve_visitor_type("non-Egyptian") == "foreigner"
    assert resolve_visitor_type("tourist") == "foreigner"
    assert resolve_visitor_type("Egyptian") == "egyptian"
    assert resolve_visitor_type("local") == "egyptian"
    assert resolve_visitor_type("martian") is None


def test_price_requires_visitor_type():
    r = check_ticket_price(1)
    assert r["ok"] is False and "visitor_type" in r["error"]


def test_price_values():
    assert check_ticket_price(1, "foreigner")["price_egp"] == 550
    assert check_ticket_price(1, "egyptian")["price_egp"] == 30


def test_zero_price_is_not_called_free():
    r = check_ticket_price(25, "foreigner")
    assert r["ok"] and r["price_egp"] == 0
    assert "verify" in r["price_note"].lower()


def test_price_unknown_inputs():
    assert check_ticket_price(999, "egyptian")["ok"] is False
    assert check_ticket_price(1, "martian")["ok"] is False