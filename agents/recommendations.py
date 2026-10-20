"""Personalised hotel-area and transport tips for multi-day trips.

The catalogue (agents/data/recommendations.json) is curated by hand; this module
only ranks and filters it for one traveller, deterministically:

  * interests   - the words the user gave (intent.interests + search_query), mapped
                  to tags such as history, beach, diving, nile, romance (weight 3);
                  the categories of the places actually planned count weakly (1)
  * budget      - economy / moderate / luxury: a hotel area without that tier is
                  pushed down, a transport tip without it is dropped
  * travelers   - solo / couple / family / group (or a head count)
  * the plan    - hotel areas are ranked by distance to the scheduled stops, and a
                  transport tip tied to specific places (West Bank taxi, Abu Simbel,
                  Giftun boat...) only appears when those places are in the plan

Every pick carries a localised `why` list so the reply and the UI can say why it fits.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from agents.attractions import get_attraction
from agents.travel import haversine_km, load_locations

DATA_PATH = Path(__file__).resolve().parent / "data" / "recommendations.json"
GREATER_CAIRO = {"Cairo", "Giza", "Greater Cairo"}

# Free-text interest words -> catalogue tags. Matching is by substring, so
# "temples" hits "temple" and "snorkelling" hits "snorkel".
INTEREST_WORDS: Dict[str, List[str]] = {
    "history": ["history", "histor", "ancient", "pharao", "temple", "tomb", "archaeolog", "monument",
                "pyramid", "egyptolog", "تاريخ", "آثار", "اثار", "فرعون", "معبد", "معابد", "مقابر", "أهرام"],
    "museums": ["museum", "art", "gallery", "mummy", "mummies", "متحف", "متاحف", "فن"],
    "culture": ["culture", "local", "bazaar", "souk", "market", "nubian", "heritage", "islamic", "coptic",
                "ثقاف", "سوق", "أسواق", "نوبي", "تراث", "إسلامي", "قبطي"],
    "food": ["food", "cuisine", "eat", "restaurant", "street food", "seafood", "أكل", "مطاعم", "مأكولات"],
    "shopping": ["shop", "souvenir", "تسوق", "شوبينج"],
    "nightlife": ["nightlife", "party", "bar", "club", "night", "سهر", "حفلات"],
    "nature": ["nature", "desert", "hik", "trek", "mountain", "camp", "safari", "sunrise", "stars", "oasis",
               "طبيعة", "صحراء", "جبل", "تخييم", "سفاري", "واحة"],
    "beach": ["beach", "sea", "swim", "resort", "sun", "شاطئ", "بحر", "سباحة", "منتجع"],
    "diving": ["div", "snorkel", "reef", "coral", "غوص", "سنوركل", "شعاب"],
    "nile": ["nile", "river", "felucca", "cruise", "boat", "sail", "نيل", "فلوكة", "مركب"],
    "relax": ["relax", "quiet", "calm", "peace", "slow", "spa", "رايق", "هادي", "هدوء", "استرخاء"],
    "romance": ["romant", "honeymoon", "anniversary", "رومانس", "شهر العسل"],
}
CATEGORY_TAGS = {
    "Museum": "museums", "Archaeological Site": "history", "Temple": "history", "Fortress": "history",
    "Monastery": "history", "Cultural Center": "culture", "National Park": "nature",
    "Aquarium": "diving", "Island / Beach": "beach", "Historic Oasis": "nature",
}
TAG_LABELS = {
    "history": ("history", "التاريخ"), "museums": ("museums", "المتاحف"), "culture": ("local culture", "الثقافة المحلية"),
    "food": ("food", "الأكل"), "shopping": ("shopping", "التسوق"), "nightlife": ("nightlife", "السهر"),
    "nature": ("nature", "الطبيعة"), "beach": ("the beach", "البحر"), "diving": ("diving", "الغوص"),
    "nile": ("the Nile", "النيل"), "relax": ("a slow pace", "الهدوء"), "romance": ("a romantic trip", "رحلة رومانسية"),
}
BUDGET_LABELS = {"economy": ("an economy", "الاقتصادية"), "moderate": ("a moderate", "المتوسطة"), "luxury": ("a luxury", "الفاخرة")}
TRAVELER_LABELS = {"solo": ("solo travellers", "المسافر لوحده"), "couple": ("couples", "الأزواج"),
                   "family": ("families", "العائلات"), "group": ("groups", "المجموعات")}
TIER_ORDER = ["moderate", "economy", "luxury"]


@lru_cache(maxsize=1)
def load_catalogue() -> Dict[str, List[Dict[str, Any]]]:
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {"hotels": data["hotels"], "transport": data["transport"]}


def canonical_region(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    return "Cairo" if region in GREATER_CAIRO else region


def interest_tags(words: Iterable[str]) -> Set[str]:
    """Map free-text interests (English or Arabic) to catalogue tags."""
    text = " ".join(str(w) for w in words if w).lower()
    return {tag for tag, keys in INTEREST_WORDS.items() if any(k in text for k in keys)}


def traveler_types(travelers: Any) -> Set[str]:
    if travelers is None or travelers == "":
        return set()
    if isinstance(travelers, (int, float)) or str(travelers).isdigit():
        n = int(travelers)
        return {"solo"} if n <= 1 else {"couple"} if n == 2 else {"family", "group"} if n <= 5 else {"group"}
    return {str(travelers).lower()} & set(TRAVELER_LABELS)


def _plan_stops(itinerary: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    stops = []
    for day in (itinerary or {}).get("days", []):
        for stop in day.get("stops", []):
            stops.append({**stop, "day": day.get("day")})
    return stops


def _label(pair: Any, ar: bool) -> str:
    return pair[1] if ar else pair[0]


def _join(items: List[str], ar: bool) -> str:
    if len(items) <= 1:
        return "".join(items)
    return (" و".join([", ".join(items[:-1]), items[-1]]) if ar
            else f"{', '.join(items[:-1])} and {items[-1]}")


def _example(examples: Dict[str, str], budget: Optional[str]) -> Optional[str]:
    if budget and budget in examples:
        return examples[budget]
    for tier in TIER_ORDER:
        if tier in examples:
            return examples[tier]
    return None


def get_recommendations(
    region: Optional[str],
    days: int,
    language: str = "en",
    *,
    interests: Optional[Iterable[str]] = None,
    search_query: Optional[str] = None,
    budget: Optional[str] = None,
    travelers: Any = None,
    itinerary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Ranked hotel areas and transport tips for one traveller (multi-day trips only).

    Returns {"hotels": [{"area", "desc", "example", "region", "why": [...]}],
             "transport": [{"mode", "desc", "region", "why": [...]}],
             "based_on": [labels of the preferences that were used]}
    """
    empty: Dict[str, Any] = {"hotels": [], "transport": [], "based_on": []}
    if not days or days < 2:
        return empty
    ar = language == "ar"
    lang = "ar" if ar else "en"

    stops = _plan_stops(itinerary)
    regions: List[str] = []
    for stop_region in [canonical_region(get_attraction(s["attraction_id"]).region) for s in stops
                        if get_attraction(s["attraction_id"])] + [canonical_region(region)]:
        if stop_region and stop_region not in regions:
            regions.append(stop_region)
    if not regions:
        return empty

    wanted = interest_tags(list(interests or []) + [search_query or ""])
    from_plan = {CATEGORY_TAGS[a.category] for a in (get_attraction(s["attraction_id"]) for s in stops)
                 if a and a.category in CATEGORY_TAGS} - wanted
    who = traveler_types(travelers)
    budget = budget if budget in BUDGET_LABELS else None
    stop_ids = {s["attraction_id"] for s in stops}
    locations = load_locations()
    catalogue = load_catalogue()

    def common_reasons(item: Dict[str, Any], why: List[str]) -> float:
        score = 0.0
        hits = [t for t in item["tags"] if t in wanted]
        if hits:
            score += 3 * len(hits)
            labels = _join([_label(TAG_LABELS[t], ar) for t in hits], ar)
            why.append(f"يناسب اهتمامك بـ{labels}" if ar else f"Suits your interest in {labels}")
        score += sum(1 for t in item["tags"] if t in from_plan)
        both = who & set(item.get("travelers", []))
        if both:
            score += 2
            labels = _join([_label(TRAVELER_LABELS[t], ar) for t in sorted(both)], ar)
            why.append(f"مناسب لـ{labels}" if ar else f"Good for {labels}")
        return score

    # ---- hotel areas: best 2 for a one-area trip, best 1 per area otherwise ----
    hotels: List[Dict[str, Any]] = []
    per_region = 2 if len(regions) == 1 else 1
    for reg in regions:
        reg_stops = [s for s in stops if canonical_region(get_attraction(s["attraction_id"]).region) == reg
                     and s["attraction_id"] in locations]
        ranked = []
        for h in (h for h in catalogue["hotels"] if h["region"] == reg):
            why: List[str] = []
            score = common_reasons(h, why)
            if budget:
                if budget in h["budgets"]:
                    score += 3
                    why.append(f"فيه اختيارات للميزانية {_label(BUDGET_LABELS[budget], ar)}" if ar
                               else f"Has options for {_label(BUDGET_LABELS[budget], ar)} budget")
                else:
                    score -= 4
            near = []
            if reg_stops:
                dists = sorted((haversine_km(h["lat"], h["lon"], locations[s["attraction_id"]]["lat"],
                                             locations[s["attraction_id"]]["lon"]), s) for s in reg_stops)
                avg = sum(d for d, _ in dists) / len(dists)
                score += max(0.0, 4 - avg / 4)
                near = [s["name"] for d, s in dists if d <= 8][:2]
            ranked.append((score, h, why, near))
        ranked.sort(key=lambda r: -r[0])
        nearest_used = False
        for score, h, why, near in ranked[:per_region]:
            if near and not nearest_used:
                names = _join(near, ar)
                why.insert(0, f"الأقرب لـ{names} في برنامجك" if ar else f"Closest to {names} in your plan")
                nearest_used = True
            hotels.append({"area": h["name"][lang], "desc": h["desc"][lang],
                           "example": _example(h.get("examples", {}), budget),
                           "region": reg, "why": why, "score": round(score, 2)})

    # ---- transport: tips tied to the plan first, then by fit; arrivals last ----
    picks, arrivals = [], []
    for t in catalogue["transport"]:
        if t["region"] not in regions:
            continue
        if budget and t.get("budgets") and budget not in t["budgets"]:
            continue
        why: List[str] = []
        score = common_reasons(t, why)
        if t.get("needs_any"):
            matched = [s["name"] for s in stops if s["attraction_id"] in t["needs_any"]]
            if not matched:
                continue
            score += 4
            names = _join(list(dict.fromkeys(matched))[:2], ar)
            why.insert(0, f"عشان {names} في برنامجك" if ar else f"For {names} in your plan")
        if t.get("needs_areas"):
            if not set(t["needs_areas"]) & set(regions):
                continue
            score += 4
            why.insert(0, "رحلتك بين أكتر من مدينة" if ar else "Your trip spans more than one city")
        entry = {"mode": t["mode"][lang], "desc": t["desc"][lang], "region": t["region"], "why": why,
                 "score": round(score, 2)}
        if t.get("arrival"):
            if len(regions) > 1 and t["region"] == regions[0]:
                continue  # the first area is where the trip starts; how to get there is the user's call
            arrivals.append(entry)
        else:
            picks.append(entry)
    picks.sort(key=lambda e: -e["score"])
    transport = picks[:3] + arrivals[:2]

    based_on = [_label(TAG_LABELS[t], ar) for t in sorted(wanted)]
    if budget:
        based_on.append(("ميزانية " + _label(BUDGET_LABELS[budget], ar).replace("ال", "", 1)) if ar
                        else f"{budget} budget")
    based_on += [_label(TRAVELER_LABELS[t], ar) for t in sorted(who)]
    return {"hotels": hotels, "transport": transport, "based_on": based_on}


# Destinations that make sense for a trip of a given length (most suitable first).
# Short trips stay where travel time doesn't eat the day.
REGIONS_BY_LENGTH = [
    (1, ["Cairo", "Alexandria"]),
    (2, ["Cairo", "Alexandria", "Luxor", "Aswan"]),
    (4, ["Luxor", "Aswan", "Cairo", "South Sinai", "Red Sea", "Alexandria"]),
    (99, ["Cairo", "Luxor", "Aswan", "Red Sea", "South Sinai", "Alexandria"]),
]
REGION_AR = {"Cairo": "القاهرة", "Giza": "الجيزة", "Luxor": "الأقصر", "Aswan": "أسوان", "Alexandria": "الإسكندرية",
             "South Sinai": "جنوب سيناء", "Red Sea": "البحر الأحمر", "Matrouh": "مطروح", "New Valley": "الوادي الجديد"}
GROUP_AR = {"solo": "لوحدك", "couple": "مع شريكك", "family": "مع العيلة", "group": "مع صحابك"}
GROUP_EN = {"solo": "solo", "couple": "for two", "family": "with the family", "group": "with friends"}


def _n(value: int, ar: bool) -> str:
    return str(value).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")) if ar else str(value)


def regions_for_days(days: Optional[int]) -> List[str]:
    """Regions worth suggesting for this trip length (all of them when the length is unknown)."""
    if not days:
        return REGIONS_BY_LENGTH[-1][1]
    return next(regions for limit, regions in REGIONS_BY_LENGTH if days <= limit)


def suggest_destinations_for_duration(days: Optional[int], language: str = "en") -> str:
    """One sentence suggesting destinations that fit the time span."""
    ar = language == "ar"
    if not days:
        return ("القاهرة للأهرامات والمتاحف، الأقصر وأسوان للمعابد والنيل، أو البحر الأحمر وسيناء للبحر والغوص."
                if ar else "Cairo for the Pyramids and museums, Luxor and Aswan for temples and the Nile, "
                           "or the Red Sea and Sinai for beaches and diving.")
    if days == 1:
        return ("في يوم واحد أحسن اختيار القاهرة (الأهرامات والمتحف المصري وخان الخليلي) أو الإسكندرية "
                "(قلعة قايتباي والمكتبة والكورنيش)." if ar else
                "For a single day, Cairo (the Pyramids, the Egyptian Museum, Khan El Khalili) or Alexandria "
                "(Qaitbay Citadel, the Library and the Corniche) work best.")
    if days == 2:
        return ("في يومين ينفع القاهرة أو الإسكندرية، أو الأقصر لو حابب المعابد." if ar else
                "Two days suit Cairo or Alexandria, or Luxor if you love temples.")
    if days <= 4:
        return (f"في {_n(days, ar)} أيام ينفع الأقصر (الكرنك ووادي الملوك)، أسوان (فيلة والنوبة)، أو شرم الشيخ ورأس محمد."
                if ar else f"{days} days suit Luxor (Karnak, Valley of the Kings), Aswan (Philae, Nubia), "
                           "or Sharm El Sheikh and Ras Mohamed.")
    return (f"في {_n(days, ar)} أيام تقدر تجمع القاهرة والأقصر، أو تاخد إجازة بحر في الغردقة والجونة." if ar else
            f"With {days} days you can combine Cairo and Luxor, or take a beach break in Hurghada and El Gouna.")


def format_clarification_message(
    missing: List[str],
    days: Optional[int] = None,
    budget: Optional[str] = None,
    travelers: Optional[Any] = None,
    language: str = "en",
    all_regions: str = "",
) -> str:
    """Ask only for what is still missing, acknowledging what the user already said.

    Budget and group size only shape hotel/transport tips, which apply to trips of
    2+ days, so a one-day trip is never asked about them.
    """
    ar = language == "ar"
    parts: List[str] = []

    known = []
    if days:
        known.append(("يوم واحد" if days == 1 else "يومين" if days == 2 else f"{_n(days, ar)} أيام") if ar
                     else ("one day" if days == 1 else f"{days} days"))
    group = next(iter(traveler_types(travelers)), None)
    if group:
        known.append(GROUP_AR[group] if ar else GROUP_EN[group])
    if known:
        parts.append(f"تمام، {' '.join(known)}." if ar else f"Got it: {', '.join(known)}.")

    if "days" in missing:
        parts.append("الرحلة كام يوم؟" if ar else "How many days do you have?")
    if "region" in missing:
        parts.append(("رايح فين؟ " if ar else "Where would you like to go? ")
                     + suggest_destinations_for_duration(days, language))

    if days and days >= 2:
        extras = []
        if not budget:
            extras.append("الميزانية (اقتصادي، متوسط، فاخر)" if ar else "your budget (economy, moderate or luxury)")
        if not group:
            extras.append("مين مسافر معاك" if ar else "who's travelling")
        if extras:
            joined = " و".join(extras) if ar else " and ".join(extras)
            parts.append(f"ولو تحب تقولّي {joined}، هختار لك فنادق ومواصلات تناسبك." if ar
                         else f"If you tell me {joined}, I'll pick hotels and transport to suit you.")

    return " ".join(parts)
