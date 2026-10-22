"""Retrieval evaluation for the RehlaGuide RAG.

Usage (from the repo root):
    uv run python -m rag.eval                  # full evaluation
    uv run python -m rag.eval --validate       # check the dataset only (no model, no DB)
    uv run python -m rag.eval --json out.json  # also save a machine-readable report
    uv run python -m rag.eval --mlflow         # also log the run to MLflow (see rag/tracking.py)
    uv run python -m rag.eval --min-hit3 0.9   # exit 1 if headline Hit@3 < 0.9 (quality gate for CI)
    uv run python -m rag.eval --min-arabic-hit3 0.7   # same, for the Arabic slice

What it measures
----------------
* Hit@K, Recall@K, Precision@K, nDCG@K at K = 1, 3, 5 and MRR@5.
* Graded relevance: 2 = the place the query is really about, 1 = acceptable.
* Slices: semantic (no filters), filtered, intent, arabic, out_of_scope.
  Filtered queries are easy by construction (a region filter leaves 2-6 of the
  30 places), so they are reported separately and never mixed into the headline.
* Filter integrity: every returned place must satisfy the filters it was asked for.
* Index health: the Chroma index must contain each raw attraction exactly once.
* Out-of-scope queries have no right answer; the report shows their best distance
  so a "no result" threshold can be calibrated.

Note: `relevance_score` returned by the retriever is a Chroma *distance*
(lower = closer), not a similarity.
"""
import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional

from rag.config import CHROMA_DB_DIR, EMBEDDING_MODEL_NAME, RAW_DATA_PATH

KS = (1, 3, 5)
MAX_K = max(KS)
METRICS = ("hit", "recall", "precision", "ndcg")

# relevant: {attraction_id: grade}, 2 = primary answer, 1 = acceptable answer.
EVAL_DATASET: List[Dict[str, Any]] = [
    # ---------------- semantic: no filters, the real test of the embeddings ----
    {"id": "sem-01", "type": "semantic", "query": "where can I see the Great Pyramid of Khufu",
     "filters": {}, "relevant": {5: 2, 6: 1, 7: 1}},
    {"id": "sem-02", "type": "semantic", "query": "royal mummies gallery",
     "filters": {}, "relevant": {2: 2, 13: 1}},
    {"id": "sem-03", "type": "semantic", "query": "how ancient Egyptians mummified bodies, canopic jars and amulets",
     "filters": {}, "relevant": {13: 2, 20: 1}},
    {"id": "sem-04", "type": "semantic", "query": "tombs of the pharaohs in a royal burial valley",
     "filters": {}, "relevant": {11: 2}},
    {"id": "sem-05", "type": "semantic", "query": "temple dedicated to the god Horus",
     "filters": {}, "relevant": {19: 2, 18: 1}},
    {"id": "sem-06", "type": "semantic", "query": "temple of the crocodile god Sobek",
     "filters": {}, "relevant": {18: 2, 20: 2}},
    {"id": "sem-07", "type": "semantic", "query": "temples that were moved to save them from flooding",
     "filters": {}, "relevant": {16: 2, 17: 2}},
    {"id": "sem-08", "type": "semantic", "query": "colossal statues of Ramesses II carved into rock",
     "filters": {}, "relevant": {17: 2, 10: 1}},
    {"id": "sem-09", "type": "semantic", "query": "ancient lighthouse Pharos of Alexandria site",
     "filters": {}, "relevant": {21: 2}},
    {"id": "sem-10", "type": "semantic", "query": "ancient library and planetarium in Alexandria",
     "filters": {}, "relevant": {22: 2}},
    {"id": "sem-11", "type": "semantic", "query": "underground tombs mixing Greek, Roman and Egyptian styles",
     "filters": {}, "relevant": {23: 2, 8: 1}},
    {"id": "sem-12", "type": "semantic", "query": "snorkeling and white sand beaches boat trip",
     "filters": {}, "relevant": {27: 2, 24: 1}},
    {"id": "sem-13", "type": "semantic", "query": "scuba diving coral reefs protected marine park",
     "filters": {}, "relevant": {24: 2, 27: 1, 26: 1}},
    {"id": "sem-14", "type": "semantic", "query": "see sharks and fish in an indoor aquarium glass tunnel",
     "filters": {}, "relevant": {26: 2}},
    {"id": "sem-15", "type": "semantic", "query": "oracle temple that Alexander the Great visited",
     "filters": {}, "relevant": {29: 2, 28: 1}},
    {"id": "sem-16", "type": "semantic", "query": "mud brick fortress in an oasis with salt lakes and hot springs",
     "filters": {}, "relevant": {28: 2, 29: 1}},
    {"id": "sem-17", "type": "semantic", "query": "desert camping and stargazing among chalk rock formations",
     "filters": {}, "relevant": {30: 2}},
    {"id": "sem-18", "type": "semantic", "query": "Christian monastery at the foot of Mount Sinai with the Burning Bush",
     "filters": {}, "relevant": {25: 2, 3: 1}},
    {"id": "sem-19", "type": "semantic", "query": "Coptic icons, manuscripts and frescoes",
     "filters": {}, "relevant": {3: 2, 25: 1}},
    {"id": "sem-20", "type": "semantic", "query": "Islamic astronomy, medicine and ceramics collection",
     "filters": {}, "relevant": {4: 2}},
    {"id": "sem-21", "type": "semantic", "query": "museum about Nubian culture and history",
     "filters": {}, "relevant": {15: 2}},
    {"id": "sem-22", "type": "semantic", "query": "Hatshepsut expedition to Punt painted reliefs",
     "filters": {}, "relevant": {12: 2, 14: 1}},
    {"id": "sem-23", "type": "semantic", "query": "great hypostyle hall with giant columns, obelisks and a sacred lake",
     "filters": {}, "relevant": {9: 2}},
    {"id": "sem-24", "type": "semantic", "query": "Step Pyramid and the Imhotep Museum",
     "filters": {}, "relevant": {6: 2}},
    {"id": "sem-25", "type": "semantic", "query": "Bent Pyramid and Red Pyramid",
     "filters": {}, "relevant": {7: 2}},
    {"id": "sem-26", "type": "semantic", "query": "underground burial place of the sacred Apis bulls",
     "filters": {}, "relevant": {8: 2}},
    {"id": "sem-27", "type": "semantic", "query": "papyri, sarcophagi, jewelry and royal statues",
     "filters": {}, "relevant": {1: 2, 2: 1}},

    # ---------------- filtered: tests filter + ranking together (easy by design) --
    {"id": "fil-01", "type": "filtered", "query": "famous ancient pyramids and royal tombs",
     "filters": {"region": "Giza"}, "relevant": {5: 2, 6: 2, 7: 2}},
    {"id": "fil-02", "type": "filtered", "query": "coptic manuscripts and religious heritage",
     "filters": {"region": "Cairo", "category": "Museum"}, "relevant": {3: 2}},
    {"id": "fil-03", "type": "filtered", "query": "underwater diving coral reefs marine life",
     "filters": {"region": "South Sinai"}, "relevant": {24: 2}},
    {"id": "fil-04", "type": "filtered", "query": "ancient temples dedicated to Horus and Sobek",
     "filters": {"region": "Aswan"}, "relevant": {19: 2, 18: 2, 20: 1}},
    {"id": "fil-05", "type": "filtered", "query": "mummies and ancient royal mummies gallery",
     "filters": {"category": "Museum"}, "relevant": {2: 2, 13: 2}},
    {"id": "fil-06", "type": "filtered", "query": "temple with colossal columns and obelisks",
     "filters": {"region": "Luxor", "category": "Temple"}, "relevant": {9: 2, 10: 1}},
    {"id": "fil-07", "type": "filtered", "query": "snorkeling island trip",
     "filters": {"region": "Red Sea"}, "relevant": {27: 2, 26: 1}},
    {"id": "fil-08", "type": "filtered", "query": "ancient oracle temple",
     "filters": {"region": "Matrouh", "category": "Temple"}, "relevant": {29: 2}},
    {"id": "fil-09", "type": "filtered", "query": "Islamic art collection",
     "filters": {"region": "Cairo", "max_duration": 1.5}, "relevant": {4: 2}},
    {"id": "fil-10", "type": "filtered", "query": "ancient Egyptian history, short visit",
     "filters": {"max_duration": 1.0}, "relevant": {13: 2, 8: 2, 20: 1, 23: 1}},

    # ---------------- intent: loose wording, no place names -------------------
    {"id": "int-01", "type": "intent", "query": "I want to see where the pharaohs were buried",
     "filters": {}, "relevant": {11: 2, 6: 1, 7: 1, 5: 1}},
    {"id": "int-02", "type": "intent", "query": "a relaxing beach day on a boat",
     "filters": {}, "relevant": {27: 2}},
    {"id": "int-03", "type": "intent", "query": "good place for kids to see sea animals",
     "filters": {}, "relevant": {26: 2, 24: 1}},
    {"id": "int-04", "type": "intent", "query": "ancient history of Alexandria",
     "filters": {}, "relevant": {21: 2, 23: 2, 22: 1}},

    # ---------------- arabic: the app targets Egyptians, but the model is English --
    {"id": "ar-01", "type": "arabic", "query": "أهرامات الجيزة",
     "filters": {}, "relevant": {5: 2, 6: 1, 7: 1}},
    {"id": "ar-02", "type": "arabic", "query": "معبد الكرنك في الأقصر",
     "filters": {}, "relevant": {9: 2}},
    {"id": "ar-03", "type": "arabic", "query": "الغوص ورؤية الشعاب المرجانية",
     "filters": {}, "relevant": {24: 2, 27: 1}},
    {"id": "ar-04", "type": "arabic", "query": "متحف المومياوات",
     "filters": {}, "relevant": {13: 2, 2: 1}},
    {"id": "ar-05", "type": "arabic", "query": "قلعة قايتباي في الإسكندرية",
     "filters": {}, "relevant": {21: 2}},
    {"id": "ar-06", "type": "arabic", "query": "معبد أبو سمبل",
     "filters": {}, "relevant": {17: 2}},
    # Egyptian-dialect and conversational phrasing (added to widen the Arabic slice)
    {"id": "ar-07", "type": "arabic", "query": "عايز اشوف الهرم الاكبر",
     "filters": {}, "relevant": {5: 2, 6: 1, 7: 1}},
    {"id": "ar-08", "type": "arabic", "query": "فين متحف الاثار المصرية القديمة",
     "filters": {}, "relevant": {1: 2, 2: 1}},
    {"id": "ar-09", "type": "arabic", "query": "وادي الملوك",
     "filters": {}, "relevant": {11: 2}},
    {"id": "ar-10", "type": "arabic", "query": "معبد حتشبسوت في الاقصر",
     "filters": {}, "relevant": {12: 2, 14: 1}},
    {"id": "ar-11", "type": "arabic", "query": "معبد فيلة في اسوان",
     "filters": {}, "relevant": {16: 2}},
    {"id": "ar-12", "type": "arabic", "query": "معبد ادفو",
     "filters": {}, "relevant": {19: 2}},
    {"id": "ar-13", "type": "arabic", "query": "مكتبة الاسكندرية",
     "filters": {}, "relevant": {22: 2}},
    {"id": "ar-14", "type": "arabic", "query": "مقابر كوم الشقافة تحت الارض",
     "filters": {}, "relevant": {23: 2}},
    {"id": "ar-15", "type": "arabic", "query": "الصحراء البيضاء والتخييم",
     "filters": {}, "relevant": {30: 2}},
    {"id": "ar-16", "type": "arabic", "query": "رحلة لواحة سيوة",
     "filters": {}, "relevant": {28: 2, 29: 1}},
    {"id": "ar-17", "type": "arabic", "query": "دير سانت كاترين وجبل موسى",
     "filters": {}, "relevant": {25: 2}},
    {"id": "ar-18", "type": "arabic", "query": "جزيرة الجفتون والسنوركل",
     "filters": {}, "relevant": {27: 2}},
    {"id": "ar-19", "type": "arabic", "query": "اكواريوم الغردقة",
     "filters": {}, "relevant": {26: 2}},
    {"id": "ar-20", "type": "arabic", "query": "راس محمد في شرم الشيخ",
     "filters": {}, "relevant": {24: 2}},
    {"id": "ar-21", "type": "arabic", "query": "المتحف القبطي",
     "filters": {}, "relevant": {3: 2}},
    {"id": "ar-22", "type": "arabic", "query": "متحف الحضارة في الفسطاط",
     "filters": {}, "relevant": {2: 2}},
    {"id": "ar-23", "type": "arabic", "query": "متحف النوبة",
     "filters": {}, "relevant": {15: 2}},
    {"id": "ar-24", "type": "arabic", "query": "معبد كوم امبو",
     "filters": {}, "relevant": {18: 2}},
    {"id": "ar-25", "type": "arabic", "query": "سقارة والهرم المدرج",
     "filters": {}, "relevant": {6: 2}},
    {"id": "ar-26", "type": "arabic", "query": "عايز اروح مكان فيه مقابر الفراعنة",
     "filters": {}, "relevant": {11: 2, 5: 1, 6: 1, 7: 1}},
    {"id": "ar-27", "type": "arabic", "query": "مكان حلو للاطفال يشوفوا فيه سمك وحيوانات البحر",
     "filters": {}, "relevant": {26: 2, 24: 1}},
    {"id": "ar-28", "type": "arabic", "query": "يوم على المركب والبحر في الغردقة",
     "filters": {}, "relevant": {27: 2}},

    # ---------------- out of scope: nothing relevant exists ------------------
    {"id": "oos-01", "type": "out_of_scope", "query": "best sushi restaurant in Tokyo",
     "filters": {}, "relevant": {}},
    {"id": "oos-02", "type": "out_of_scope", "query": "how to renew a passport",
     "filters": {}, "relevant": {}},
    {"id": "oos-03", "type": "out_of_scope", "query": "Eiffel Tower and the Louvre in Paris",
     "filters": {}, "relevant": {}},
    {"id": "oos-04", "type": "out_of_scope", "query": "football match results yesterday",
     "filters": {}, "relevant": {}},
    {"id": "oos-05", "type": "out_of_scope", "query": "احسن مطعم سوشي في طوكيو",
     "filters": {}, "relevant": {}},
    {"id": "oos-06", "type": "out_of_scope", "query": "نتيجة مباراة الاهلي امبارح",
     "filters": {}, "relevant": {}},
]


# --------------------------------------------------------------------------- #
# Dataset validation (offline)
# --------------------------------------------------------------------------- #
def load_raw() -> Dict[int, Dict[str, Any]]:
    with open(RAW_DATA_PATH, "r", encoding="utf-8") as f:
        return {int(item["id"]): item for item in json.load(f)}


def passes_filters(item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Mirror of the filter logic in rag.retriever.search_attractions."""
    if filters.get("region") and item.get("region", item.get("city")) != filters["region"]:
        return False
    if filters.get("category") and item.get("category") != filters["category"]:
        return False
    if filters.get("max_duration") is not None:
        if float(item.get("estimated_visit_duration_min", 0)) / 60.0 > filters["max_duration"]:
            return False
    return True


def validate_dataset() -> List[str]:
    """Return a list of problems; an empty list means the labels are consistent."""
    raw = load_raw()
    problems: List[str] = []
    seen = set()
    for case in EVAL_DATASET:
        cid = case["id"]
        if cid in seen:
            problems.append(f"{cid}: duplicate case id")
        seen.add(cid)
        if case["type"] != "out_of_scope" and not case["relevant"]:
            problems.append(f"{cid}: no relevant ids")
        if case["type"] != "out_of_scope" and not any(g == 2 for g in case["relevant"].values()):
            problems.append(f"{cid}: no primary (grade 2) answer")
        for doc_id, grade in case["relevant"].items():
            if doc_id not in raw:
                problems.append(f"{cid}: id {doc_id} does not exist in raw_attractions.json")
            elif not passes_filters(raw[doc_id], case["filters"]):
                problems.append(
                    f"{cid}: id {doc_id} ({raw[doc_id]['name']}) is labelled relevant "
                    f"but is excluded by the case's own filters {case['filters']}"
                )
            if grade not in (1, 2):
                problems.append(f"{cid}: id {doc_id} has invalid grade {grade}")
    return problems


# --------------------------------------------------------------------------- #
# Index health (needs the Chroma folder, not the embedding model)
# --------------------------------------------------------------------------- #
def check_index_health() -> Dict[str, Any]:
    import chromadb

    raw_ids = set(load_raw())
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("langchain")  # langchain-chroma default name
    metas = collection.get(include=["metadatas"])["metadatas"]
    indexed = [int(m["id"]) for m in metas]
    counts: Dict[int, int] = defaultdict(int)
    for i in indexed:
        counts[i] += 1
    return {
        "indexed_rows": len(indexed),
        "distinct_attractions": len(counts),
        "raw_attractions": len(raw_ids),
        "missing_ids": sorted(raw_ids - set(counts)),
        "duplicated_ids": sorted(i for i, c in counts.items() if c > 1),
        "healthy": set(counts) == raw_ids and all(c == 1 for c in counts.values()),
    }


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def score_case(retrieved_ids: List[int], relevant: Dict[int, int]) -> Dict[str, float]:
    rel_set = set(relevant)
    out: Dict[str, float] = {}
    for k in KS:
        top = retrieved_ids[:k]
        found = [i for i in top if i in rel_set]
        out[f"hit@{k}"] = 1.0 if found else 0.0
        out[f"recall@{k}"] = len(set(found)) / len(rel_set)
        out[f"precision@{k}"] = len(found) / k
        dcg = sum(relevant.get(doc, 0) / math.log2(rank + 1)
                  for rank, doc in enumerate(top, start=1))
        ideal = sorted(relevant.values(), reverse=True)[:k]
        idcg = sum(g / math.log2(rank + 1) for rank, g in enumerate(ideal, start=1))
        out[f"ndcg@{k}"] = dcg / idcg if idcg else 0.0
    out["mrr"] = next(
        (1.0 / rank for rank, doc in enumerate(retrieved_ids[:MAX_K], start=1) if doc in rel_set),
        0.0,
    )
    return out


def dedupe(ids: List[int]) -> List[int]:
    seen, out = set(), []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def mean(values: List[float]) -> float:
    return statistics.fmean(values) if values else 0.0


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run_cases(search_fn: Callable[..., List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    raw = load_raw()
    results = []
    for case in EVAL_DATASET:
        f = case["filters"]
        hits = search_fn(
            query=case["query"],
            region=f.get("region"),
            category=f.get("category"),
            max_duration=f.get("max_duration"),
            top_k=MAX_K,
        )
        retrieved = [int(h["metadata"]["id"]) for h in hits]
        unique = dedupe(retrieved)
        violations = [i for i in unique if i in raw and not passes_filters(raw[i], f)]
        row = {
            "id": case["id"],
            "type": case["type"],
            "query": case["query"],
            "filters": f,
            "relevant": case["relevant"],
            "retrieved": unique,
            "duplicates_in_topk": len(retrieved) - len(unique),
            "filter_violations": violations,
            "top1_distance": float(hits[0]["relevance_score"]) if hits else None,
        }
        if case["relevant"]:
            row["scores"] = score_case(unique, case["relevant"])
        results.append(row)
    return results


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored = [r for r in results if "scores" in r]

    def agg(rows: List[Dict[str, Any]]) -> Dict[str, float]:
        keys = rows[0]["scores"].keys() if rows else []
        return {k: mean([r["scores"][k] for r in rows]) for k in keys}

    by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in scored:
        by_type[r["type"]].append(r)

    # Headline = unfiltered, English queries only (semantic + intent).
    headline_rows = [r for r in scored if r["type"] in ("semantic", "intent")]
    in_scope_d = [r["top1_distance"] for r in scored
                  if r["type"] in ("semantic", "intent") and r["top1_distance"] is not None]
    oos_d = [r["top1_distance"] for r in results
             if r["type"] == "out_of_scope" and r["top1_distance"] is not None]

    return {
        "headline": agg(headline_rows),
        "headline_n": len(headline_rows),
        "by_type": {t: {"n": len(rows), **agg(rows)} for t, rows in by_type.items()},
        "filter_violations": sum(1 for r in results if r["filter_violations"]),
        "cases_with_duplicates": sum(1 for r in results if r["duplicates_in_topk"]),
        "distance": {
            "in_scope_top1_mean": mean(in_scope_d),
            "out_of_scope_top1_mean": mean(oos_d),
            "out_of_scope_top1_min": min(oos_d) if oos_d else None,
            "in_scope_top1_max": max(in_scope_d) if in_scope_d else None,
        },
    }


def pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def print_report(health: Optional[Dict[str, Any]], results: List[Dict[str, Any]],
                 summary: Dict[str, Any]) -> None:
    print("=" * 72)
    print("RehlaGuide RAG - retrieval evaluation")
    print(f"Embedding model: {EMBEDDING_MODEL_NAME}")
    print("=" * 72)

    if health is not None:
        print("\n[Index health]")
        print(f"  indexed rows: {health['indexed_rows']} | distinct attractions: "
              f"{health['distinct_attractions']} / {health['raw_attractions']} in raw data")
        if health["missing_ids"]:
            print(f"  MISSING from index: {health['missing_ids']}")
        if health["duplicated_ids"]:
            print(f"  DUPLICATED in index: {health['duplicated_ids']}")
        print("  status:", "OK" if health["healthy"] else
              "UNHEALTHY - re-ingest from scratch before trusting the numbers below")

    print("\n[Headline: unfiltered semantic + intent queries, n="
          f"{summary['headline_n']}]")
    h = summary["headline"]
    print(f"  {'K':>3} | {'Hit':>7} {'Recall':>7} {'Prec':>7} {'nDCG':>7}")
    for k in KS:
        print(f"  {k:>3} | {pct(h[f'hit@{k}'])} {pct(h[f'recall@{k}'])} "
              f"{pct(h[f'precision@{k}'])} {pct(h[f'ndcg@{k}'])}")
    print(f"  MRR@{MAX_K}: {h['mrr']:.3f}")

    print("\n[By slice @ K=3]")
    print(f"  {'slice':<13} {'n':>3} | {'Hit':>7} {'Recall':>7} {'nDCG':>7} {'MRR':>6}")
    for t, s in summary["by_type"].items():
        print(f"  {t:<13} {s['n']:>3} | {pct(s['hit@3'])} {pct(s['recall@3'])} "
              f"{pct(s['ndcg@3'])} {s['mrr']:>6.3f}")

    print(f"\n[Filter integrity] cases returning a place that breaks its filters: "
          f"{summary['filter_violations']}")
    print(f"[Duplicates]       cases with the same place twice in top-{MAX_K}: "
          f"{summary['cases_with_duplicates']}")

    d = summary["distance"]
    print("\n[Out-of-scope calibration] (Chroma distance, lower = closer)")
    print(f"  in-scope top-1:     mean {d['in_scope_top1_mean']:.3f}, worst {d['in_scope_top1_max']:.3f}"
          if d["in_scope_top1_max"] is not None else "  in-scope: n/a")
    print(f"  out-of-scope top-1: mean {d['out_of_scope_top1_mean']:.3f}, best {d['out_of_scope_top1_min']:.3f}"
          if d["out_of_scope_top1_min"] is not None else "  out-of-scope: n/a")
    print("  A usable 'no result' cutoff must sit between these two ranges.")

    failures = [r for r in results if "scores" in r and r["scores"]["hit@3"] == 0.0]
    print(f"\n[Failures: no relevant place in top-3] {len(failures)} case(s)")
    for r in failures:
        print(f"  {r['id']} '{r['query']}' filters={r['filters']}")
        print(f"      expected {sorted(r['relevant'])} | got {r['retrieved'][:3]}")
    print("=" * 72)


def ensure_utf8_output(stream: Any = None) -> None:
    """Make printing Arabic safe on consoles whose default encoding is not UTF-8.

    On Windows the console encoding is often cp1252, and printing the Arabic queries in
    the failure list crashed the run before the MLflow logging step. No-op for streams
    that cannot be reconfigured (e.g. when output is captured)."""
    stream = stream if stream is not None else sys.stdout
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8", errors="replace")


def check_thresholds(summary: Dict[str, Any], min_hit3: Optional[float] = None,
                     min_mrr: Optional[float] = None,
                     min_arabic_hit3: Optional[float] = None) -> List[str]:
    """Quality gate for CI: returns one message per metric below its minimum.

    min_hit3 / min_mrr apply to the headline (English, unfiltered) queries;
    min_arabic_hit3 applies to the Arabic slice, so a regression in Arabic retrieval
    cannot hide behind good English numbers."""
    headline = summary["headline"]
    failures = []
    if min_hit3 is not None and headline["hit@3"] < min_hit3:
        failures.append(f"headline Hit@3 {headline['hit@3']:.3f} is below the minimum {min_hit3:.3f}")
    if min_mrr is not None and headline["mrr"] < min_mrr:
        failures.append(f"headline MRR {headline['mrr']:.3f} is below the minimum {min_mrr:.3f}")
    if min_arabic_hit3 is not None:
        arabic = summary.get("by_type", {}).get("arabic")
        if arabic is None:
            failures.append("no Arabic cases were scored, so --min-arabic-hit3 cannot be checked")
        elif arabic["hit@3"] < min_arabic_hit3:
            failures.append(f"Arabic Hit@3 {arabic['hit@3']:.3f} is below the minimum {min_arabic_hit3:.3f}")
    return failures


def evaluate_retriever(search_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
                       json_path: Optional[str] = None,
                       skip_health: bool = False,
                       mlflow_options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run the evaluation. `mlflow_options` (experiment / run_name / tracking_uri, all
    optional) turns on MLflow logging; None leaves it off."""
    problems = validate_dataset()
    if problems:
        raise SystemExit("Dataset is inconsistent:\n  " + "\n  ".join(problems))

    if mlflow_options is not None:
        from rag import tracking
        if not tracking.mlflow_available():  # fail before the slow part, not after it
            raise SystemExit("MLflow is not installed. Run: uv sync --extra tracking")

    if search_fn is None:
        from rag.retriever import search_attractions
        search_fn = search_attractions

    health = None if skip_health else check_index_health()
    results = run_cases(search_fn)
    summary = summarize(results)
    print_report(health, results, summary)

    from rag.tracking import dataset_fingerprint
    report = {"embedding_model": EMBEDDING_MODEL_NAME, "index_health": health,
              "dataset_size": len(EVAL_DATASET), "dataset_hash": dataset_fingerprint(EVAL_DATASET),
              "summary": summary, "cases": results}
    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"Saved JSON report to {json_path}")
    if mlflow_options is not None:
        run_id = tracking.log_eval_run(report, **mlflow_options)
        print(f"Logged MLflow run {run_id} "
              f"(UI: uv run mlflow ui --backend-store-uri {tracking.resolve_tracking_uri(mlflow_options.get('tracking_uri'))})")
    return report


if __name__ == "__main__":
    ensure_utf8_output()
    parser = argparse.ArgumentParser(description="Evaluate the RehlaGuide retriever.")
    parser.add_argument("--validate", action="store_true",
                        help="only check that the labelled dataset is consistent")
    parser.add_argument("--json", metavar="PATH", help="save a JSON report")
    parser.add_argument("--mlflow", action="store_true",
                        help="log metrics, params and the report to MLflow (needs: uv sync --extra tracking)")
    parser.add_argument("--experiment", default=None, help="MLflow experiment name")
    parser.add_argument("--run-name", default=None, help="MLflow run name (default: the embedding model)")
    parser.add_argument("--tracking-uri", default=None,
                        help="MLflow tracking URI (default: $MLFLOW_TRACKING_URI or a local mlflow.db)")
    parser.add_argument("--min-hit3", type=float, default=None,
                        help="fail (exit code 1) if the headline Hit@3 is below this value, e.g. 0.9")
    parser.add_argument("--min-mrr", type=float, default=None,
                        help="fail (exit code 1) if the headline MRR@5 is below this value")
    parser.add_argument("--min-arabic-hit3", type=float, default=None,
                        help="fail (exit code 1) if the Arabic-slice Hit@3 is below this value")
    args = parser.parse_args()

    if args.validate:
        issues = validate_dataset()
        if issues:
            raise SystemExit("Dataset problems:\n  " + "\n  ".join(issues))
        print(f"Dataset OK: {len(EVAL_DATASET)} cases, all ids and filters consistent.")
    else:
        options = None
        if args.mlflow:
            from rag.tracking import DEFAULT_EXPERIMENT
            options = {"experiment": args.experiment or DEFAULT_EXPERIMENT,
                       "run_name": args.run_name, "tracking_uri": args.tracking_uri}
        final = evaluate_retriever(json_path=args.json, mlflow_options=options)
        problems = check_thresholds(final["summary"], args.min_hit3, args.min_mrr, args.min_arabic_hit3)
        if problems:
            raise SystemExit("Quality gate failed:\n  " + "\n  ".join(problems))
