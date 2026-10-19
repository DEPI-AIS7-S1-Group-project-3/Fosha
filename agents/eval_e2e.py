"""End-to-end evaluation of Arabic search: the path a real user takes.

rag.eval sends Arabic text straight to the retriever. The product does not: Gemini
first turns the message into an English search query (agents.intent), and only then
does retrieval run. This script measures that real path and compares three ways:

  raw_ar        Arabic message -> retriever directly (what rag.eval measures; no LLM)
  pipeline_ar   Arabic message -> Gemini intent -> English query -> retriever
  pipeline_en   English message -> Gemini intent -> retriever (the upper bound)

If pipeline_ar is close to pipeline_en, Arabic is already fine and a multilingual
embedding model is not needed. If it is far, the "translated query" column in the
failure list shows whether the translation or the retrieval is at fault.

Usage (repo root; needs GEMINI_API_KEY in .env, and a built index):
    uv run python -m agents.eval_e2e                    # all three paths
    uv run python -m agents.eval_e2e --no-english       # skip pipeline_en (half the Gemini calls)
    uv run python -m agents.eval_e2e --delay 2          # wait 2 s between Gemini calls (rate limits)
    uv run python -m agents.eval_e2e --json e2e.json
    uv run python -m agents.eval_e2e --validate         # check the labels only (no key, no model)

Messages are phrased like a real request ("I want to visit ..."), because a bare place
name may be classified as "not a trip" by the intent step. Both numbers are reported:
retrieval quality (scored from the extracted query) and how many messages were
not classified as a trip request.
"""
import argparse
import json
import time
from typing import Any, Callable, Dict, List, Optional

from agents.intent import extract_intent
from agents.retrieval_adapter import GREATER_CAIRO, search_attractions as adapter_search
from rag.eval import MAX_K, dedupe, load_raw, mean, pct, score_case

LLMFn = Callable[..., Dict[str, Any]]
SearchFn = Callable[..., List[Dict[str, Any]]]

# relevant: {attraction_id: grade}, 2 = the place asked about, 1 = acceptable.
# region: the region the intent step should extract (None = the message names none).
CASES: List[Dict[str, Any]] = [
    # ---- named places: tests that the translation keeps the right place name ----
    {"id": "n-01", "ar": "عايز أزور أهرامات الجيزة", "en": "I want to visit the Giza pyramids",
     "relevant": {5: 2, 6: 1, 7: 1}, "region": None},
    {"id": "n-02", "ar": "عايز أزور معبد الكرنك", "en": "I want to visit Karnak Temple",
     "relevant": {9: 2}, "region": None},
    {"id": "n-03", "ar": "عايز أشوف وادي الملوك", "en": "I want to see the Valley of the Kings",
     "relevant": {11: 2}, "region": None},
    {"id": "n-04", "ar": "عايز أروح معبد أبو سمبل", "en": "I want to go to the Abu Simbel temple",
     "relevant": {17: 2}, "region": None},
    {"id": "n-05", "ar": "عايز أزور متحف التحنيط", "en": "I want to visit the Mummification Museum",
     "relevant": {13: 2, 2: 1}, "region": None},
    {"id": "n-06", "ar": "عايز أزور قلعة قايتباي", "en": "I want to visit the Citadel of Qaitbay",
     "relevant": {21: 2}, "region": None},
    {"id": "n-07", "ar": "عايز أزور مكتبة الإسكندرية", "en": "I want to visit the Bibliotheca Alexandrina",
     "relevant": {22: 2}, "region": None},
    {"id": "n-08", "ar": "عايز أزور دير سانت كاترين", "en": "I want to visit Saint Catherine's Monastery",
     "relevant": {25: 2}, "region": None},
    {"id": "n-09", "ar": "عايز أروح الصحراء البيضاء", "en": "I want to go to the White Desert",
     "relevant": {30: 2}, "region": None},
    {"id": "n-10", "ar": "عايز أزور واحة سيوة", "en": "I want to visit Siwa Oasis",
     "relevant": {28: 2, 29: 1}, "region": None},
    {"id": "n-11", "ar": "عايز أروح جزيرة الجفتون", "en": "I want to go to Giftun Island",
     "relevant": {27: 2}, "region": None},
    {"id": "n-12", "ar": "عايز أزور المتحف المصري", "en": "I want to visit the Egyptian Museum",
     "relevant": {1: 2, 2: 1}, "region": None},
    {"id": "n-13", "ar": "عايز أزور معبد فيلة", "en": "I want to visit Philae Temple",
     "relevant": {16: 2}, "region": None},
    {"id": "n-14", "ar": "عايز أزور معبد حتشبسوت", "en": "I want to visit Hatshepsut Temple",
     "relevant": {12: 2, 14: 1}, "region": None},
    {"id": "n-15", "ar": "عايز أزور المتحف القبطي", "en": "I want to visit the Coptic Museum",
     "relevant": {3: 2}, "region": None},
    {"id": "n-16", "ar": "عايز أزور متحف الفن الإسلامي", "en": "I want to visit the Museum of Islamic Art",
     "relevant": {4: 2}, "region": None},
    # ---- descriptive / dialect: no place name, tests understanding ----
    {"id": "d-01", "ar": "بحب الغوص والشعاب المرجانية، تنصحني بإيه؟",
     "en": "I love diving and coral reefs, what do you recommend?",
     "relevant": {24: 2, 27: 1}, "region": None},
    {"id": "d-02", "ar": "عايز أشوف المقابر الملكية بتاعة الفراعنة",
     "en": "I want to see the royal tombs of the pharaohs",
     "relevant": {11: 2, 6: 1, 7: 1, 5: 1}, "region": None},
    {"id": "d-03", "ar": "إيه مكان حلو للأطفال يشوفوا فيه سمك وأسماك قرش؟",
     "en": "What is a good place for kids to see fish and sharks?",
     "relevant": {26: 2, 24: 1}, "region": None},
    {"id": "d-04", "ar": "عايز أزور معبد بتاع الإله حورس",
     "en": "I want to visit the temple of the god Horus",
     "relevant": {19: 2, 18: 1}, "region": None},
    # ---- region in the message: tests region extraction + filtering ----
    {"id": "r-01", "ar": "عايز أزور المعابد في الأقصر", "en": "I want to visit the temples in Luxor",
     "relevant": {9: 2, 10: 2, 12: 2}, "region": "Luxor"},
    {"id": "r-02", "ar": "عايز أزور المتاحف في القاهرة", "en": "I want to visit the museums in Cairo",
     "relevant": {1: 2, 2: 2, 3: 2, 4: 2}, "region": "Cairo"},
    {"id": "r-03", "ar": "عايز أزور المعابد في أسوان", "en": "I want to visit the temples in Aswan",
     "relevant": {16: 2, 17: 2, 18: 2, 19: 2}, "region": "Aswan"},
]

PATHS = ("raw_ar", "pipeline_ar", "pipeline_en")


# --------------------------------------------------------------------------- #
# Label validation (offline)
# --------------------------------------------------------------------------- #
def validate_cases() -> List[str]:
    raw = load_raw()
    problems: List[str] = []
    seen = set()
    for case in CASES:
        cid = case["id"]
        if cid in seen:
            problems.append(f"{cid}: duplicate id")
        seen.add(cid)
        if not case["ar"].strip() or not case["en"].strip():
            problems.append(f"{cid}: empty message")
        if not any(g == 2 for g in case["relevant"].values()):
            problems.append(f"{cid}: no primary (grade 2) answer")
        allowed = None
        if case["region"]:
            allowed = set(GREATER_CAIRO) if case["region"] == "Cairo" else {case["region"]}
        for doc_id, grade in case["relevant"].items():
            if doc_id not in raw:
                problems.append(f"{cid}: id {doc_id} is not in raw_attractions.json")
            elif allowed and raw[doc_id]["region"] not in allowed:
                problems.append(f"{cid}: id {doc_id} is outside region {case['region']}")
            if grade not in (1, 2):
                problems.append(f"{cid}: id {doc_id} has invalid grade {grade}")
    return problems


# --------------------------------------------------------------------------- #
# The three paths
# --------------------------------------------------------------------------- #
def run_raw(message: str, search_fn: SearchFn) -> Dict[str, Any]:
    """Message straight to the retriever, no LLM."""
    try:
        hits = search_fn(query=message, top_k=MAX_K)
        ids = dedupe([int(h["metadata"]["id"]) for h in hits])
    except Exception as exc:  # model missing, index missing, ...
        return {"error": f"retrieval failed: {exc}", "retrieved": []}
    return {"error": None, "retrieved": ids, "query": message, "region": None, "task": None}


def run_pipeline(message: str, llm: LLMFn, search_fn: SearchFn) -> Dict[str, Any]:
    """Gemini intent -> query + region -> the same adapter call the planner makes."""
    extracted = extract_intent(message, llm)
    if not extracted["ok"]:
        return {"error": extracted["error"], "retrieved": []}
    intent = extracted["intent"]
    found = adapter_search(intent["search_query"], region=intent["region"], top_k=MAX_K,
                           apply_cutoff=False, search_fn=search_fn)
    if not found["ok"]:
        return {"error": found["error"], "retrieved": [], "query": intent["search_query"],
                "region": intent["region"], "task": intent["task"]}
    ids = dedupe([r["attraction"]["id"] for r in found["results"]])
    return {"error": None, "retrieved": ids, "query": intent["search_query"],
            "region": intent["region"], "task": intent["task"]}


# --------------------------------------------------------------------------- #
# Runner and report
# --------------------------------------------------------------------------- #
def run_all(llm: LLMFn, search_fn: SearchFn, include_english: bool = True,
            delay: float = 0.0, rows: Optional[List[Dict[str, Any]]] = None,
            progress: Optional[Callable[[int, int, Dict[str, Any], float], None]] = None
            ) -> List[Dict[str, Any]]:
    """Runs every case. `rows` is filled as it goes, so a Ctrl+C keeps what finished."""
    rows = [] if rows is None else rows
    for number, case in enumerate(CASES, start=1):
        started = time.time()
        row: Dict[str, Any] = {"id": case["id"], "ar": case["ar"], "en": case["en"],
                               "relevant": case["relevant"], "expected_region": case["region"],
                               "paths": {}}
        row["paths"]["raw_ar"] = run_raw(case["ar"], search_fn)
        row["paths"]["pipeline_ar"] = run_pipeline(case["ar"], llm, search_fn)
        if delay:
            time.sleep(delay)
        if include_english:
            row["paths"]["pipeline_en"] = run_pipeline(case["en"], llm, search_fn)
            if delay:
                time.sleep(delay)
        for result in row["paths"].values():
            result["scores"] = score_case(result["retrieved"], case["relevant"])
        rows.append(row)
        if progress:
            progress(number, len(CASES), row, time.time() - started)
    return rows


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"n": len(rows), "paths": {}}
    for path in PATHS:
        results = [r["paths"][path] for r in rows if path in r["paths"]]
        if not results:
            continue
        scores = {k: mean([x["scores"][k] for x in results]) for k in results[0]["scores"]}
        entry: Dict[str, Any] = {"scores": scores, "errors": sum(1 for x in results if x["error"])}
        if path != "raw_ar":
            entry["not_a_trip"] = sum(1 for x in results if x.get("task") not in (None, "plan_trip"))
            wrong_region = 0
            for r in rows:
                res = r["paths"].get(path)
                if res and not res["error"] and res.get("region") != r["expected_region"]:
                    wrong_region += 1
            entry["wrong_region"] = wrong_region
        out["paths"][path] = entry
    return out


def print_report(rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    print("=" * 76)
    print("RehlaGuide - Arabic end-to-end evaluation")
    print("=" * 76)
    print(f"cases: {summary['n']}\n")
    head = f"  {'path':<12} | {'Hit@1':>7} {'Hit@3':>7} {'Rec@3':>7} {'nDCG@3':>7} {'MRR':>6} | errors  not-a-trip  wrong-region"
    print(head)
    for path, e in summary["paths"].items():
        s = e["scores"]
        extra = (f"{e['errors']:>6}  {e['not_a_trip']:>11}  {e['wrong_region']:>12}"
                 if path != "raw_ar" else f"{e['errors']:>6}  {'-':>11}  {'-':>12}")
        print(f"  {path:<12} | {pct(s['hit@1'])} {pct(s['hit@3'])} {pct(s['recall@3'])} "
              f"{pct(s['ndcg@3'])} {s['mrr']:>6.3f} | {extra}")

    ar = summary["paths"].get("pipeline_ar")
    en = summary["paths"].get("pipeline_en")
    if ar and en:
        gap = (en["scores"]["hit@3"] - ar["scores"]["hit@3"]) * 100
        print(f"\nArabic gap vs English through the same pipeline (Hit@3): {gap:+.1f} points")
        print("  small gap  -> Arabic already works via translation; no new embedding model needed")
        print("  large gap  -> read the failure list: wrong translation, or wrong retrieval?")

    bad_llm = [r for r in rows if any(p["error"] for p in r["paths"].values())]
    if bad_llm:
        print(f"\n[Errors] {len(bad_llm)} case(s) had an LLM or retrieval error; rerun them "
              "(scored as misses above):")
        for r in bad_llm:
            for name, p in r["paths"].items():
                if p["error"]:
                    print(f"  {r['id']} {name}: {p['error'][:110]}")

    failures = [r for r in rows if r["paths"]["pipeline_ar"]["scores"]["hit@3"] == 0.0
                and not r["paths"]["pipeline_ar"]["error"]]
    print(f"\n[pipeline_ar failures: nothing relevant in top-3] {len(failures)} case(s)")
    for r in failures:
        p = r["paths"]["pipeline_ar"]
        print(f"  {r['id']} {r['ar']}")
        print(f"      translated query: {p['query']!r} | region: {p['region']}")
        print(f"      expected {sorted(r['relevant'])} | got {p['retrieved'][:3]}")

    odd = [r for r in rows if not r["paths"]["pipeline_ar"]["error"]
           and r["paths"]["pipeline_ar"].get("region") != r["expected_region"]]
    if odd:
        print(f"\n[Region extraction differs from the label] {len(odd)} case(s)")
        for r in odd:
            print(f"  {r['id']} {r['ar']} -> region {r['paths']['pipeline_ar']['region']} "
                  f"(expected {r['expected_region']})")
    print("=" * 76)


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end Arabic evaluation.")
    parser.add_argument("--validate", action="store_true", help="check the labels only")
    parser.add_argument("--no-english", action="store_true", help="skip the English pipeline path")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between Gemini calls")
    parser.add_argument("--json", metavar="PATH", help="save a JSON report")
    args = parser.parse_args()

    problems = validate_cases()
    if problems:
        raise SystemExit("Label problems:\n  " + "\n  ".join(problems))
    if args.validate:
        print(f"Labels OK: {len(CASES)} cases, all ids and regions consistent.")
        return

    from agents.llm import generate
    from rag.retriever import search_attractions as rag_search

    print("Checking Gemini (one small call)...", flush=True)
    probe = generate("ping", json_mode=False)
    if not probe.get("ok"):
        raise SystemExit(f"Gemini is not reachable: {probe.get('error')}\n"
                         "Check GEMINI_API_KEY / GEMINI_MODEL in your .env.")
    calls = len(CASES) * (2 if args.no_english else 3)
    print(f"Gemini OK ({probe.get('model')}). Running {len(CASES)} cases, "
          f"{calls - len(CASES)} Gemini calls; Ctrl+C prints the results so far.\n", flush=True)

    def show(number: int, total: int, row: Dict[str, Any], seconds: float) -> None:
        marks = "  ".join(
            f"{name}={'hit' if res['scores']['hit@3'] else ('ERR' if res['error'] else 'miss')}"
            for name, res in row["paths"].items())
        print(f"[{number:>2}/{total}] {row['id']}  {marks}  ({seconds:.1f}s)", flush=True)

    rows: List[Dict[str, Any]] = []
    try:
        run_all(generate, rag_search, include_english=not args.no_english, delay=args.delay,
                rows=rows, progress=show)
    except KeyboardInterrupt:
        print(f"\nStopped early: {len(rows)} of {len(CASES)} cases finished.\n")
    if not rows:
        raise SystemExit("No case finished.")
    summary = summarize(rows)
    print_report(rows, summary)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "cases": rows}, f, ensure_ascii=False, indent=2)
        print(f"Saved JSON report to {args.json}")


if __name__ == "__main__":
    main()
