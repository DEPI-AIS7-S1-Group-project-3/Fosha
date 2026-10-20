"""Places beyond the curated dataset: any Egyptian city or town the user names.

The 30 curated attractions (data/raw_attractions.json) only cover the regions on
the globe. For anywhere else in Egypt ("بورسعيد", "Ismailia", "Fayoum"...) we look
the place up in open, citable sources instead of letting the LLM invent places:

  1. Nominatim (OpenStreetMap) geocodes the name, restricted to Egypt.
  2. Wikivoyage's page for that place supplies the "See" listings: names,
     descriptions, and sometimes coordinates, hours and prices, written for travellers.
  3. Wikidata fills in missing coordinates and Arabic names.

Found places are registered next to the curated ones (ids from DYNAMIC_ID_START),
so the scheduler applies exactly the same rules to them. Anything a source does
not state is marked as unknown rather than guessed: hours default to a daytime
window flagged "uncertain" (the plan says "check before you go"), and prices
stay unknown unless the listing gives one.

Results are cached on disk (data/places_cache.json, gitignored), so each place is
fetched once. Every network call has a short timeout and failures return
{"ok": False, "reason": "offline"} instead of raising.
"""
import hashlib
import json
import re
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agents.attractions import Attraction, load_attractions
from agents.hours import load_hours
from agents.travel import haversine_km, load_locations

USER_AGENT = ("Fosha-RehlaGuide/0.1 (DEPI capstone travel assistant; "
              "https://github.com/DEPI-AIS7-S1-Group-project-3/RehlaGuide)")
NOMINATIM = "https://nominatim.openstreetmap.org/search"
WIKIVOYAGE = "https://en.wikivoyage.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "places_cache.json"
CACHE_VERSION = 5          # bump when the stored record format changes; older entries are refetched
DYNAMIC_ID_START = 100_000
MAX_DISTANCE_KM = 40      # listings farther than this from the town centre are dropped
TIMEOUT_S = 8

Fetch = Callable[[str, Dict[str, Any]], Any]
_lock = threading.Lock()
_arabic_names: Dict[int, str] = {}   # registered id -> Arabic name (from Wikidata), for the UI
_arabic_areas: Dict[str, str] = {}   # town name (the scheduler's area) -> Arabic name

# Category from words in the listing's name/description, most specific first.
CATEGORY_RULES = [
    ("Museum", ["museum", "gallery", "متحف"]),
    ("Religious Site", ["mosque", "church", "cathedral", "monastery", "synagogue", "basilica", "shrine", "مسجد", "كنيسة", "دير"]),
    ("Temple", ["temple", "معبد"]),
    ("Archaeological Site", ["ruin", "tomb", "necropolis", "archaeolog", "ancient city", "pyramid"]),
    ("Fortress", ["fort", "citadel", "castle", "قلعة", "طابية"]),
    ("Island / Beach", ["beach", "island", "bay", "شاطئ", "جزيرة"]),
    ("Park / Promenade", ["park", "garden", "corniche", "promenade", "walkway", "zoo", "lake", "حديقة", "كورنيش"]),
    ("Landmark", []),
]
DURATION_MIN = {"Museum": 90, "Archaeological Site": 90, "Temple": 90, "Fortress": 60, "Religious Site": 30,
                "Island / Beach": 120, "Park / Promenade": 60, "Landmark": 30}


# ---------------------------------------------------------------- HTTP + cache
def http_json(url: str, params: Dict[str, Any]) -> Any:
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _load_cache(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) and data.get("_version") == CACHE_VERSION else {}


def _save_cache(path: Path, cache: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # a read-only disk only costs us the cache


# ---------------------------------------------------------------- wikitext helpers
def _split_top(body: str) -> List[str]:
    """Split a template body on '|' that are not inside [[...]] or {{...}}."""
    parts, depth, cur, i = [], 0, [], 0
    while i < len(body):
        two = body[i:i + 2]
        if two in ("[[", "{{"):
            depth += 1; cur.append(two); i += 2; continue
        if two in ("]]", "}}"):
            depth = max(0, depth - 1); cur.append(two); i += 2; continue
        if body[i] == "|" and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(body[i])
        i += 1
    parts.append("".join(cur))
    return parts


def clean_wikitext(text: str) -> str:
    text = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", text, flags=re.S)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", text)          # [[a|b]] -> b
    text = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", text)              # [url label] -> label
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)                                 # inline templates
    text = re.sub(r"<[^>]+>", "", text).replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", text).strip()


def parse_listings(wikitext: str, kinds=("see",)) -> List[Dict[str, str]]:
    """Wikivoyage {{see|name=...|lat=...|long=...|hours=...|price=...|content=...}} listings."""
    out = []
    for m in re.finditer(r"\{\{\s*(see|do)\s*\n?\s*\|((?:[^{}]|\{\{[^{}]*\}\})*)\}\}", wikitext, re.I):
        if m.group(1).lower() not in kinds:
            continue
        fields: Dict[str, str] = {}
        for part in _split_top(m.group(2)):
            if "=" in part:
                key, value = part.split("=", 1)
                fields[key.strip().lower()] = value.strip()
        name = clean_wikitext(fields.get("name", ""))
        if name:
            out.append({"kind": m.group(1).lower(), "name": name,
                        **{k: clean_wikitext(fields.get(k, "")) for k in
                           ("alt", "lat", "long", "hours", "price", "content", "wikidata", "url")}})
    return out


# ---------------------------------------------------------------- field parsing
def _to_minutes(h: int, m: int, ampm: str) -> int:
    ampm = (ampm or "").lower().replace(".", "")
    if ampm.startswith("p") and h < 12:
        h += 12
    if ampm.startswith("a") and h == 12:
        h = 0
    return h * 60 + m


def parse_hours(text: str) -> Optional[List[str]]:
    """First "9AM-5PM" / "09:00–17:00" style range in free text, as ["HH:MM", "HH:MM"]."""
    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*([ap]\.?m\.?)?\s*(?:-|–|—|to)\s*"
                  r"(\d{1,2})(?:[:.](\d{2}))?\s*([ap]\.?m\.?)?", text or "", re.I)
    if not m:
        return None
    start = _to_minutes(int(m.group(1)), int(m.group(2) or 0), m.group(3) or "")
    end = _to_minutes(int(m.group(4)), int(m.group(5) or 0), m.group(6) or "")
    if not m.group(6) and not m.group(3) and end <= start and int(m.group(4)) < 12:
        end += 12 * 60  # "9-5" means 09:00-17:00
    if not 0 <= start < end <= 24 * 60:
        return None
    return [f"{start // 60:02d}:{start % 60:02d}", f"{end // 60:02d}:{end % 60:02d}"]


def parse_price(text: str) -> Optional[float]:
    """A single EGP amount ("Entry 5 EGP", "LE 60", "£E20"); None if absent or ambiguous."""
    if re.search(r"\bfree\b|مجان", text or "", re.I):
        return 0.0
    m = re.search(r"(?:(?:EGP|LE|L\.E\.|£E)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:EGP|LE|L\.E\.|£E|pounds?|جنيه))",
                  text or "", re.I)
    return float(m.group(1) or m.group(2)) if m else None


def categorise(name: str, content: str) -> str:
    text = f"{name} {content}".lower()
    for category, words in CATEGORY_RULES:
        if not words or any(w in text for w in words):
            return category
    return "Landmark"


def _float(value: str) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stable_id(city: str, name: str) -> int:
    digest = hashlib.sha1(f"{city}|{name}".lower().encode("utf-8")).hexdigest()
    return DYNAMIC_ID_START + int(digest[:8], 16) % 800_000


# ---------------------------------------------------------------- lookups
def geocode(name: str, fetch: Fetch = http_json) -> Optional[Dict[str, Any]]:
    hits = fetch(NOMINATIM, {"q": name, "countrycodes": "eg", "format": "jsonv2", "limit": 1,
                             "accept-language": "en", "namedetails": 1, "extratags": 1})
    if not hits:
        return None
    hit = hits[0]
    names = hit.get("namedetails") or {}
    # Every spelling we know, for finding the Wikivoyage page ("Al Ismailiya" vs "Ismailia")
    # The city's Wikidata item names its exact Wikivoyage page, whatever language the user typed in.
    voyage_title = None
    qid = (hit.get("extratags") or {}).get("wikidata")
    if qid:
        links = fetch(WIKIDATA, {"action": "wbgetentities", "ids": qid, "props": "sitelinks",
                                 "sitefilter": "enwikivoyage", "format": "json"})
        voyage_title = (((((links or {}).get("entities") or {}).get(qid) or {}).get("sitelinks") or {})
                        .get("enwikivoyage") or {}).get("title")
    spellings = [voyage_title, names.get("name:en"), hit.get("name"), names.get("alt_name:en"), name]
    spellings = [s for s in dict.fromkeys(spellings) if s and re.search(r"[A-Za-z]", s)]
    return {"name": names.get("name:en") or hit.get("name") or name, "name_ar": names.get("name:ar") or names.get("name"),
            "lat": float(hit["lat"]), "lon": float(hit["lon"]), "display": hit.get("display_name", ""),
            "spellings": spellings}


def wikivoyage_page(spellings: List[str], fetch: Fetch = http_json) -> Optional[Dict[str, str]]:
    """The Wikivoyage page with "See" listings for the first spelling that has one."""
    def parse(title: str) -> Optional[Dict[str, str]]:
        data = fetch(WIKIVOYAGE, {"action": "parse", "page": title, "prop": "wikitext",
                                  "format": "json", "formatversion": 2, "redirects": 1})
        page = (data or {}).get("parse")
        return {"title": page["title"], "wikitext": page["wikitext"]} if page else None

    def has_listings(page: Optional[Dict[str, str]]) -> bool:
        return bool(page) and re.search(r"\{\{\s*(see|do)\s*\|", page["wikitext"], re.I) is not None

    fallback = None
    for title in spellings:
        page = parse(title)
        if has_listings(page):
            return page
        fallback = fallback or page
    for title in spellings[:2]:
        found = fetch(WIKIVOYAGE, {"action": "query", "list": "search", "srsearch": f"{title} Egypt",
                                   "srlimit": 3, "format": "json", "formatversion": 2})
        for hit in ((found or {}).get("query") or {}).get("search") or []:
            page = parse(hit["title"])
            if has_listings(page):
                return page
    return fallback


def wikidata_details(qids: List[str], fetch: Fetch = http_json) -> Dict[str, Dict[str, Any]]:
    """{qid: {"lat", "lon", "name_ar"}} for the listings that link a Wikidata item."""
    qids = [q for q in qids if re.fullmatch(r"Q\d+", q or "")]
    if not qids:
        return {}
    data = fetch(WIKIDATA, {"action": "wbgetentities", "ids": "|".join(qids[:50]), "props": "claims|labels",
                            "languages": "ar", "format": "json"})
    out = {}
    for qid, entity in ((data or {}).get("entities") or {}).items():
        info: Dict[str, Any] = {"name_ar": ((entity.get("labels") or {}).get("ar") or {}).get("value")}
        coord = ((entity.get("claims") or {}).get("P625") or [{}])[0]
        value = (((coord.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {})
        if "latitude" in value:
            info.update(lat=value["latitude"], lon=value["longitude"])
        out[qid] = info
    return out


def translate_names(names: List[str], llm: Callable[..., Dict[str, Any]]) -> Dict[str, str]:
    """Arabic names for places Wikidata has no Arabic label for: one small LLM call per town,
    stored in the cache. Only names are translated; no facts come from the model."""
    if not names:
        return {}
    prompt = ("Translate these Egyptian place names into Arabic, literally. Translate only the words that are "
              "there: never add saints, people, dedications or descriptions that are not in the English name "
              "(e.g. 'Port Said Military Museum' -> 'متحف بورسعيد الحربي', 'Cathedral of the Holy Virgin' -> "
              "'كاتدرائية العذراء'). Use the usual Egyptian Coptic form for saints' names (Saint Bishoy -> الأنبا بيشوي). "
              "Reply with one JSON object mapping each English name exactly as given to its Arabic name.\n"
              + json.dumps(names, ensure_ascii=False))
    result = llm(prompt, system=None, json_mode=True)
    try:
        data = json.loads(result.get("text") or "{}") if result.get("ok") else {}
    except ValueError:
        return {}
    # Models sometimes tweak the key (case, accents, spacing): match on a normalised form.
    norm = lambda text: re.sub(r"[^a-z0-9]", "", text.lower())
    by_norm = {norm(n): n for n in names}
    out = {}
    for key, value in data.items():
        name = key if key in names else by_norm.get(norm(str(key)))
        if name and isinstance(value, str) and re.search(r"[\u0600-\u06FF]", value):
            out[name] = value.strip()
    return out


def find_places(place: str, fetch: Fetch = http_json, cache_path: Optional[Path] = None,
                llm: Optional[Callable[..., Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Look up visitor attractions for any place in Egypt.

    Returns {"ok": True, "city": {...}, "places": [record, ...], "source": url}
         or {"ok": False, "reason": "not_found" | "no_listings" | "offline", "city": {...}?}
    """
    cache_path = cache_path or CACHE_PATH
    key = re.sub(r"\s+", " ", place.strip().lower())
    cache = _load_cache(cache_path)
    if key in cache:
        return cache[key]
    try:
        city = geocode(place, fetch)
        if city is None:
            result: Dict[str, Any] = {"ok": False, "reason": "not_found"}
        else:
            page = wikivoyage_page(city.get("spellings") or [city["name"]], fetch)
            listings = parse_listings(page["wikitext"]) if page else []
            if len(listings) < 3 and page:  # small towns: activities count too
                listings += parse_listings(page["wikitext"], kinds=("do",))
            extra = wikidata_details([l["wikidata"] for l in listings], fetch)
            places = []
            for item in listings:
                wd = extra.get(item["wikidata"], {})
                lat, lon = _float(item["lat"]) or wd.get("lat"), _float(item["long"]) or wd.get("lon")
                approximate = lat is None or lon is None
                if approximate:
                    lat, lon = city["lat"], city["lon"]
                if haversine_km(lat, lon, city["lat"], city["lon"]) > MAX_DISTANCE_KM:
                    continue
                category = categorise(item["name"], item["content"])
                places.append({
                    "id": stable_id(city["name"], item["name"]), "name": item["name"],
                    "name_ar": wd.get("name_ar"), "city": city["name"], "region": city["name"],
                    "city_ar": city.get("name_ar"),
                    "category": category, "description": item["content"] or item["alt"],
                    "hours_text": item["hours"], "window": parse_hours(item["hours"]),
                    "price_text": item["price"], "price_egp": parse_price(item["price"]),
                    "duration_min": DURATION_MIN[category], "lat": lat, "lon": lon,
                    "approximate_location": approximate,
                    "source_url": f"https://en.wikivoyage.org/wiki/{urllib.parse.quote(page['title'].replace(' ', '_'))}",
                })
            if places and llm is not None:
                missing = [p["name"] for p in places if not p["name_ar"]]
                arabic = translate_names(missing, llm)
                for p in places:
                    p["name_ar"] = p["name_ar"] or arabic.get(p["name"])
            result = ({"ok": True, "city": city, "places": places} if places
                      else {"ok": False, "reason": "no_listings", "city": city})
    except Exception:  # network down, rate limited, unexpected payload
        return {"ok": False, "reason": "offline"}
    with _lock:
        cache["_version"] = CACHE_VERSION
        cache[key] = result
        _save_cache(cache_path, cache)
    return result


# ---------------------------------------------------------------- registration
def register_places(places: List[Dict[str, Any]]) -> List[int]:
    """Make found places visible to the scheduler, pricing and travel tools. Returns their ids."""
    attractions, hours, locations = load_attractions(), load_hours(), load_locations()
    ids = []
    with _lock:
        for p in places:
            pid = p["id"]
            price = p["price_egp"]
            attractions[pid] = Attraction(
                id=pid, name=p["name"], city=p["city"], region=p["region"], category=p["category"],
                description=p["description"] or "", opening_hours_text=p["hours_text"] or "not listed",
                price_egyptian_egp=price, price_foreigner_egp=price, duration_min=p["duration_min"],
                source_url=p["source_url"], last_verified="Wikivoyage (live)",
            )
            window = p["window"]
            hours[pid] = {
                "default": [window or ["09:00", "17:00"]], "overrides": {}, "confidence": "uncertain",
                "note": (f"Listed as: {p['hours_text']}" if p["hours_text"]
                         else "Opening hours aren't listed; check before you go"),
            }
            locations[pid] = {"lat": p["lat"], "lon": p["lon"],
                              "note": "Approximate location (town centre)" if p["approximate_location"] else ""}
            if p.get("name_ar"):
                _arabic_names[pid] = p["name_ar"]
            if p.get("city_ar"):
                _arabic_areas[p["region"]] = p["city_ar"]
            ids.append(pid)
    return ids


def arabic_name(attraction_id: int) -> Optional[str]:
    return _arabic_names.get(attraction_id)


def arabic_area(area: str) -> Optional[str]:
    return _arabic_areas.get(area)


def is_dynamic(attraction_id: int) -> bool:
    return attraction_id >= DYNAMIC_ID_START
