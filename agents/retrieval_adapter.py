"""The agent calls search_attractions() from THIS file, never Member 1's directly.
That way, if Member 1 changes how retrieval works inside, only this file changes.

What it adds on top of rag.retriever.search_attractions:
  * checks region/category against the real data (case-insensitive)
  * treats "Cairo" as Greater Cairo = Cairo + Giza (the Pyramids are filed under Giza)
  * removes duplicate places and drops results that are too far from the query
  * attaches the full record (hours, prices, ...) from agents.attractions
  * never raises: it always returns {"ok": ..., ...}
"""
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

from agents import telemetry
from agents.attractions import get_attraction, load_attractions

# Chroma distance, lower = closer. From Member 1's eval: worst in-scope top-1 was
# 1.372, best out-of-scope top-1 was 1.391. The gap is tiny, so treat this as a
# soft signal and recalibrate when we add more attractions.
DISTANCE_CUTOFF = 1.38

GREATER_CAIRO = ("Cairo", "Giza")
GREATER_CAIRO_NAMES = {"cairo", "greater cairo"}  # "giza" alone searches Giza only


def _error(message: str) -> Dict[str, Any]:
    return {"ok": False, "error": message}


def _default_search_fn() -> Callable[..., List[Dict[str, Any]]]:
    # Imported here, not at the top, so importing this file does not load the
    # embedding model, and tests can pass in a fake search function instead.
    from rag.retriever import search_attractions as rag_search

    return rag_search


def search_attractions(
    query: str,
    region: Optional[str] = None,
    category: Optional[str] = None,
    max_duration_hours: Optional[float] = None,
    top_k: int = 5,
    apply_cutoff: bool = True,
    search_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Tool contract. Returns one of:
        {"ok": True, "results": [{"attraction": {...}, "distance": 0.93}, ...],
         "dropped_too_far": int, "unknown_ids": [ids not found in the raw data]}
        {"ok": False, "error": "human-readable reason"}
    results are sorted best match first. The query should be English for now.
    apply_cutoff=False keeps weak matches (used when planning inside a named region,
    where relevance should only ORDER the places, not remove them).
    """
    if not isinstance(query, str) or not query.strip():
        return _error("query must be a non-empty string")

    # Valid values come from the data itself, so they never go out of date.
    known = list(load_attractions().values())
    valid_regions = {a.region.lower(): a.region for a in known}
    valid_categories = {a.category.lower(): a.category for a in known}

    regions_to_search: List[Optional[str]] = [None]  # None = no region filter
    if region:
        key = str(region).strip().lower()
        if key in GREATER_CAIRO_NAMES:
            regions_to_search = list(GREATER_CAIRO)
        elif key in valid_regions:
            regions_to_search = [valid_regions[key]]
        else:
            return _error(
                f"Unknown region {region!r}. Valid regions: {sorted(valid_regions.values())}"
            )

    category_value: Optional[str] = None
    if category:
        key = str(category).strip().lower()
        if key not in valid_categories:
            return _error(
                f"Unknown category {category!r}. Valid categories: {sorted(valid_categories.values())}"
            )
        category_value = valid_categories[key]

    # Member 1's filter accepts ONE region at a time, so Greater Cairo = 2 calls.
    search = search_fn or _default_search_fn()
    hits: List[Dict[str, Any]] = []
    try:
        for one_region in regions_to_search:
            hits.extend(
                search(
                    query=query,
                    region=one_region,
                    category=category_value,
                    max_duration=max_duration_hours,
                    top_k=top_k,
                )
            )
    except Exception as exc:  # retriever down, model missing, bad DB, numpy incompatibility...
        if search_fn is None:
            try:
                from api.demo import demo_search
                for one_region in regions_to_search:
                    hits.extend(demo_search(query=query, region=one_region, category=category_value, top_k=top_k))
            except Exception:
                return _error(f"Retrieval failed: {exc}")
        else:
            return _error(f"Retrieval failed: {exc}")

    # One entry per place, keeping its best (lowest) distance.
    best_distance: Dict[int, float] = {}
    try:
        for hit in hits:
            attraction_id = int(hit["metadata"]["id"])
            distance = float(hit["relevance_score"])
            if attraction_id not in best_distance or distance < best_distance[attraction_id]:
                best_distance[attraction_id] = distance
    except (KeyError, TypeError, ValueError) as exc:
        return _error(f"Malformed retriever output: {exc!r}")

    results: List[Dict[str, Any]] = []
    dropped_too_far = 0
    unknown_ids: List[int] = []
    for attraction_id, distance in sorted(best_distance.items(), key=lambda pair: pair[1]):
        if apply_cutoff and distance > DISTANCE_CUTOFF:
            dropped_too_far += 1
            continue
        attraction = get_attraction(attraction_id)
        if attraction is None:  # index and raw JSON out of sync
            unknown_ids.append(attraction_id)
            continue
        results.append({"attraction": asdict(attraction), "distance": round(distance, 4)})

    telemetry.record_retrieval(top1_distance=min(best_distance.values()) if best_distance else None,
                               n_results=len(results[:top_k]), dropped_too_far=dropped_too_far)
    return {
        "ok": True,
        "results": results[:top_k],
        "dropped_too_far": dropped_too_far,
        "unknown_ids": unknown_ids,
    }