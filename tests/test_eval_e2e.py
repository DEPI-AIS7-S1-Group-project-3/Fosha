"""Arabic end-to-end eval: labels, the three paths and the report. Fake LLM, fake search."""
import json

from agents import eval_e2e as e2e


def by_message():
    table = {}
    for case in e2e.CASES:
        table[case["ar"]] = case
        table[case["en"]] = case
    return table


def make_llm(task="plan_trip", translate=True):
    """Fake Gemini: returns an intent whose search_query encodes the case id."""
    table = by_message()

    def llm(prompt, system=None, json_mode=False):
        case = table[prompt]
        query = f"case:{case['id']}" if translate else "banana"
        return {"ok": True, "text": json.dumps({
            "task": task, "language": "ar", "search_query": query,
            "region": case["region"], "days": 2})}
    return llm


def make_search():
    """Fake retriever: understands 'case:<id>' (a good translation) and raw Arabic text."""
    table = by_message()
    cases = {c["id"]: c for c in e2e.CASES}

    def search(query, region=None, category=None, max_duration=None, top_k=5):
        case = cases.get(query[5:]) if query.startswith("case:") else table.get(query)
        if case is None:
            return []
        ranked = sorted(case["relevant"], key=lambda i: -case["relevant"][i])
        return [{"metadata": {"id": i}, "relevance_score": 0.5 + 0.1 * n}
                for n, i in enumerate(ranked[:top_k])]
    return search


def test_labels_are_consistent():
    assert e2e.validate_cases() == []


def test_cases_cover_names_descriptions_and_regions():
    assert len(e2e.CASES) >= 20
    assert any(c["region"] for c in e2e.CASES)
    assert any(c["id"].startswith("d-") for c in e2e.CASES)


def test_pipeline_uses_the_translated_query_and_region():
    case = next(c for c in e2e.CASES if c["id"] == "r-02")  # museums in Cairo
    result = e2e.run_pipeline(case["ar"], make_llm(), make_search())
    assert result["error"] is None
    assert result["query"] == "case:r-02" and result["region"] == "Cairo"
    assert set(result["retrieved"]) == set(case["relevant"])


def test_pipeline_reports_llm_failure_instead_of_raising():
    def broken(prompt, system=None, json_mode=False):
        return {"ok": False, "error": "503 overloaded"}
    result = e2e.run_pipeline("عايز أزور معبد الكرنك", broken, make_search())
    assert result["retrieved"] == [] and "503" in result["error"]


def test_raw_path_sends_the_arabic_text_unchanged():
    seen = []

    def spy(query, region=None, category=None, max_duration=None, top_k=5):
        seen.append(query)
        return []
    e2e.run_raw("عايز أزور معبد الكرنك", spy)
    assert seen == ["عايز أزور معبد الكرنك"]


def test_perfect_translation_scores_perfectly_and_no_region_errors():
    rows = e2e.run_all(make_llm(), make_search())
    summary = e2e.summarize(rows)
    for path in ("raw_ar", "pipeline_ar", "pipeline_en"):
        assert summary["paths"][path]["scores"]["hit@3"] == 1.0
    assert summary["paths"]["pipeline_ar"]["wrong_region"] == 0
    assert summary["paths"]["pipeline_ar"]["errors"] == 0


def test_bad_translation_shows_up_as_misses_and_in_the_failure_list(capsys):
    rows = e2e.run_all(make_llm(translate=False), make_search(), include_english=False)
    summary = e2e.summarize(rows)
    assert summary["paths"]["pipeline_ar"]["scores"]["hit@3"] == 0.0
    assert "pipeline_en" not in summary["paths"]
    e2e.print_report(rows, summary)
    out = capsys.readouterr().out
    assert "translated query: 'banana'" in out


def test_not_a_trip_is_counted_separately():
    rows = e2e.run_all(make_llm(task="other"), make_search(), include_english=False)
    summary = e2e.summarize(rows)
    assert summary["paths"]["pipeline_ar"]["not_a_trip"] == len(e2e.CASES)
    assert summary["paths"]["pipeline_ar"]["scores"]["hit@3"] == 1.0  # retrieval itself was fine


def test_report_prints_the_gap_line(capsys):
    rows = e2e.run_all(make_llm(), make_search())
    e2e.print_report(rows, e2e.summarize(rows))
    assert "Arabic gap vs English" in capsys.readouterr().out


def test_progress_callback_and_caller_owned_rows_survive_an_interrupt():
    seen, rows = [], []

    def progress(number, total, row, seconds):
        seen.append((number, total, row["id"]))
        if number == 3:
            raise KeyboardInterrupt

    try:
        e2e.run_all(make_llm(), make_search(), rows=rows, progress=progress)
    except KeyboardInterrupt:
        pass
    assert [n for n, _, _ in seen] == [1, 2, 3]
    assert len(rows) == 3          # finished cases are kept for the partial report
    assert e2e.summarize(rows)["n"] == 3
