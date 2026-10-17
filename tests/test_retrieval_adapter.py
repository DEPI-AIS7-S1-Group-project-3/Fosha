"""Milestone 1 (adapter): uses a FAKE search function, so no Chroma or model is needed."""
from agents.retrieval_adapter import DISTANCE_CUTOFF, search_attractions


def hit(attraction_id, distance):
    return {"content": "", "metadata": {"id": attraction_id}, "relevance_score": distance}


def make_fake(hits_by_region):
    calls = []

    def fake(query, region=None, category=None, max_duration=None, top_k=5):
        calls.append({"region": region, "category": category, "max_duration": max_duration})
        return hits_by_region.get(region, [])
    fake.calls = calls
    return fake


def ids(result):
    return [r["attraction"]["id"] for r in result["results"]]


def test_cairo_searches_cairo_and_giza_and_sorts_by_distance():
    fake = make_fake({"Cairo": [hit(1, 0.9)], "Giza": [hit(5, 0.7)]})
    r = search_attractions("museums", region="cairo", search_fn=fake)
    assert r["ok"] and ids(r) == [5, 1]
    assert [c["region"] for c in fake.calls] == ["Cairo", "Giza"]


def test_giza_alone_searches_giza_only():
    fake = make_fake({"Giza": [hit(5, 0.7)]})
    search_attractions("pyramids", region="Giza", search_fn=fake)
    assert [c["region"] for c in fake.calls] == ["Giza"]


def test_duplicates_collapse_to_best_distance():
    fake = make_fake({None: [hit(1, 1.1), hit(1, 0.8), hit(1, 0.95)]})
    r = search_attractions("x", search_fn=fake)
    assert ids(r) == [1] and r["results"][0]["distance"] == 0.8


def test_too_far_results_are_dropped_and_counted():
    fake = make_fake({None: [hit(1, 0.9), hit(2, DISTANCE_CUTOFF + 0.1)]})
    r = search_attractions("x", search_fn=fake)
    assert ids(r) == [1] and r["dropped_too_far"] == 1


def test_unknown_id_from_index_is_reported_not_crashed():
    fake = make_fake({None: [hit(999, 0.5), hit(1, 0.6)]})
    r = search_attractions("x", search_fn=fake)
    assert ids(r) == [1] and r["unknown_ids"] == [999]


def test_category_and_duration_are_forwarded_case_insensitive():
    fake = make_fake({None: []})
    search_attractions("x", category="museum", max_duration_hours=2.0, search_fn=fake)
    assert fake.calls[0]["category"] == "Museum" and fake.calls[0]["max_duration"] == 2.0


def test_bad_arguments_return_errors():
    fake = make_fake({})
    assert search_attractions("", search_fn=fake)["ok"] is False
    assert search_attractions("x", region="Atlantis", search_fn=fake)["ok"] is False
    assert search_attractions("x", category="Spaceport", search_fn=fake)["ok"] is False
    assert fake.calls == []


def test_retriever_failure_becomes_error_not_exception():
    def broken(**kwargs):
        raise RuntimeError("db missing")
    r = search_attractions("x", search_fn=broken)
    assert r["ok"] is False and "db missing" in r["error"]


def test_malformed_retriever_output():
    r = search_attractions("x", search_fn=lambda **k: [{"oops": 1}])
    assert r["ok"] is False