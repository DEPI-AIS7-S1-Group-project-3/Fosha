"""Arabic versions of the plan's free text (descriptions, hours and place notes,
warnings), so an Arabic plan shows no English sentences.

The facts stay in English in the data; this only translates text that is shown.
One batched model call per plan for strings not seen before, cached on disk
(data/translations_cache.json, gitignored), so each sentence is translated once.
A translation that loses or changes any time or number (e.g. "Closed between
14:00 and 17:00") is discarded and the English kept: wording may change, facts may not.
"""
import json
import re
import threading
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "translations_cache.json"
_ARABIC = re.compile(r"[؀-ۿ]")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_NUMBERS = re.compile(r"\d{1,2}:\d{2}|\d+(?:\.\d+)?")
_lock = threading.Lock()
BATCH = 40

SYSTEM = (
    "You translate short travel-plan texts from English into clear Modern Standard Arabic as used in Egypt. "
    "Reply with ONE JSON object mapping each input key to its Arabic translation. Keep every time, number "
    "and price exactly as written (24-hour HH:MM). Keep proper names of places recognisable (use the usual "
    "Arabic name if there is one). Do not add or remove information."
)


def _load(path: Path) -> Dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(path: Path, cache: Dict[str, str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def keeps_facts(source: str, translated: str) -> bool:
    """Every time/number in the English must appear in the Arabic (Arabic digits allowed)."""
    wanted = _NUMBERS.findall(source)
    have = translated.translate(_ARABIC_DIGITS)
    return all(n in have for n in wanted)


def to_arabic(texts: Iterable[str], llm: Callable[..., Dict[str, Any]],
              cache_path: Optional[Path] = None) -> Dict[str, str]:
    """{english: arabic} for the given texts (already-Arabic or empty texts are skipped).
    Missing entries mean "keep the English" (model down, or a translation that changed a fact)."""
    path = cache_path or CACHE_PATH
    unique = list(dict.fromkeys(t.strip() for t in texts if t and t.strip() and not _ARABIC.search(t)))
    cache = _load(path)
    todo = [t for t in unique if t not in cache]
    for start in range(0, len(todo), BATCH):
        chunk = todo[start:start + BATCH]
        keyed = {str(i): text for i, text in enumerate(chunk)}
        result = llm(json.dumps(keyed, ensure_ascii=False), system=SYSTEM, json_mode=True)
        try:
            out = json.loads(result["text"]) if result.get("ok") else {}
        except (ValueError, TypeError):
            out = {}
        for key, text in keyed.items():
            arabic = out.get(key)
            if isinstance(arabic, str) and _ARABIC.search(arabic) and keeps_facts(text, arabic):
                cache[text] = arabic.strip()
    if todo:
        with _lock:
            merged = {**_load(path), **cache}
            _save(path, merged)
            cache = merged
    return {t: cache[t] for t in unique if t in cache}


def localize_itinerary(itinerary: Dict[str, Any], llm: Callable[..., Dict[str, Any]],
                       cache_path: Optional[Path] = None) -> Dict[str, Any]:
    """Add Arabic copies (`*_ar`) of the itinerary's English free text, in place."""
    texts: List[str] = []
    for day in itinerary.get("days", []):
        texts += day.get("warnings", []) + day.get("notes", [])
        for stop in day.get("stops", []):
            texts += [stop.get("description") or "", stop.get("hours_note") or "", stop.get("place_note") or ""]
    texts += itinerary.get("warnings", [])
    texts += [u.get("reason") or "" for u in itinerary.get("unscheduled", [])]
    arabic = to_arabic(texts, llm, cache_path)
    tr = lambda text: arabic.get((text or "").strip(), text)
    for day in itinerary.get("days", []):
        day["warnings_ar"] = [tr(w) for w in day.get("warnings", [])]
        day["notes_ar"] = [tr(n) for n in day.get("notes", [])]
        for stop in day.get("stops", []):
            for field in ("description", "hours_note", "place_note"):
                if stop.get(field):
                    stop[f"{field}_ar"] = tr(stop[field])
    itinerary["warnings_ar"] = [tr(w) for w in itinerary.get("warnings", [])]
    for u in itinerary.get("unscheduled", []):
        u["reason_ar"] = tr(u.get("reason"))
    return itinerary
