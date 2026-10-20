"""Offline demo mode (REHLA_DEMO=1): a rule-based stand-in for Gemini and the
vector store, so the UI can be developed and presented without an API key,
the embedding model or a Chroma index.

It plugs into the real pipeline (plan_trip -> scheduler -> guard) through the
same `llm` and `search_fn` hooks the tests use, so hours, travel and prices are
still computed by the real code. Only understanding and wording are faked.
"""
import json
import re
from typing import Any, Dict, List, Optional

from agents.attractions import load_attractions
from agents.places_online import arabic_area
from agents.recommendations import REGION_AR

AREA_AR = {**REGION_AR, "Greater Cairo": "القاهرة الكبرى"}

REGION_WORDS = {
    "Cairo": ["cairo", "giza", "pyramid", "القاهرة", "الجيزة", "الاهرامات", "الأهرامات", "مصر القديمة"],
    "Luxor": ["luxor", "الأقصر", "الاقصر"],
    "Aswan": ["aswan", "abu simbel", "أسوان", "اسوان", "أبو سمبل"],
    "Alexandria": ["alexandria", "alex", "الإسكندرية", "الاسكندرية", "اسكندرية"],
    "South Sinai": ["sinai", "sharm", "saint catherine", "سيناء", "شرم", "سانت كاترين"],
    "Red Sea": ["hurghada", "red sea", "الغردقة", "البحر الأحمر"],
    "Matrouh": ["siwa", "matrouh", "سيوة", "مطروح"],
    "New Valley": ["white desert", "farafra", "new valley", "الصحراء البيضاء", "الفرافرة", "الوادي الجديد"],
}
# Places outside the curated regions (real Gemini recognises any name; the demo needs a list).
# They are looked up online by agents/places_online.py.
OTHER_PLACES = {
    "Port Said": ["port said", "بورسعيد", "بور سعيد"], "Ismailia": ["ismailia", "الإسماعيلية", "الاسماعيلية"],
    "Suez": ["suez", "السويس"], "Fayoum": ["fayoum", "faiyum", "الفيوم"], "Dahab": ["dahab", "دهب"],
    "Marsa Alam": ["marsa alam", "مرسى علم"], "El Alamein": ["alamein", "العلمين"],
    "Rosetta": ["rosetta", "rashid", "رشيد"], "Damietta": ["damietta", "دمياط"], "Tanta": ["tanta", "طنطا"],
    "Mansoura": ["mansoura", "المنصورة"], "Minya": ["minya", "المنيا"], "Asyut": ["asyut", "assiut", "أسيوط", "اسيوط"],
    "Sohag": ["sohag", "سوهاج"], "Qena": ["qena", "قنا"], "Beni Suef": ["beni suef", "بني سويف"],
    "Nuweiba": ["nuweiba", "نويبع"], "Taba": ["taba", "طابا"], "El Quseir": ["quseir", "القصير"],
    "Safaga": ["safaga", "سفاجا"], "Ain Sokhna": ["sokhna", "السخنة"], "Bahariya": ["bahariya", "الواحات البحرية"],
}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "a week": 7, "weekend": 2, "واحد": 1, "يومين": 2, "يومان": 2, "ثلاث": 3, "ثلاثة": 3,
                "أربع": 4, "اربع": 4, "أربعة": 4, "خمس": 5, "خمسة": 5, "ستة": 6, "أسبوع": 7, "اسبوع": 7}
INTERESTS = {
    "museums": ["museum", "متحف", "متاحف"], "history": ["history", "histor", "تاريخ", "آثار", "اثار"],
    "temples": ["temple", "معبد", "معابد"], "beach": ["beach", "sea", "شاطئ", "بحر"],
    "diving": ["diving", "snorkel", "غوص"], "desert": ["desert", "صحراء"],
    "islamic": ["islamic", "إسلامي", "اسلامي"], "coptic": ["coptic", "قبطي"],
    "nile": ["nile", "felucca", "river", "نيل", "فلوكة"], "relax": ["relax", "quiet", "calm", "رايق", "هدوء", "استرخاء"],
    "romance": ["romant", "honeymoon", "رومانس", "شهر العسل"], "nature": ["nature", "hik", "mountain", "طبيعة", "جبل"],
    "food": ["food", "eat", "أكل"], "culture": ["culture", "local", "nubian", "ثقاف", "نوبي"],
}
DAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS_AR = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
TRIP_WORDS = ["trip", "plan", "itinerary", "visit", "days", "day", "رحلة", "برنامج", "أزور", "ازور", "يوم", "أيام", "ايام"]


def _has_arabic(text: str) -> bool:
    return bool(re.search(r"[؀-ۿ]", text))


def _extract(message: str) -> Dict[str, Any]:
    text = message.lower().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    region = next((r for r, words in REGION_WORDS.items() if any(w in text for w in words)), None)
    unsupported = None if region else next(
        (name for name, words in OTHER_PLACES.items() if any(w in text for w in words)), None)

    days: Optional[int] = None
    match = re.search(r"(\d+)\s*(?:-?\s*days?|-?\s*nights?|يوم|أيام|ايام)", text)
    if match:
        days = int(match.group(1))
    else:
        for word, n in sorted(NUMBER_WORDS.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text):
                days = n
                break
        # "a day trip", "رحلة يوم", or "يوم" on its own all mean one day
        if days is None and re.search(r"(?<!\w)(a|one) day|day trip|يوم واحد|(?<!\w)يوم(?!\w)", text):
            days = 1

    interests = [name for name, words in INTERESTS.items() if any(w in text for w in words)]
    weekday = next((d for d in DAYS_EN if d in text), None)
    if weekday is None:
        weekday = next((DAYS_EN[i] for i, d in enumerate(DAYS_AR) if d in text), None)
    visitor = None
    if any(w in text for w in ("foreign", "tourist", "أجنبي", "اجنبي", "سائح")):
        visitor = "foreigner"
    elif any(w in text for w in ("egyptian", "local", "مصري")):
        visitor = "egyptian"

    # Specific tiers first: "moderate budget" must not read as economy just because it says "budget".
    budget = None
    if any(w in text for w in ("luxury", "luxurious", "vip", "deluxe", "5 star", "five star", "فاخر", "راقي", "٥ نجوم")):
        budget = "luxury"
    elif any(w in text for w in ("moderat", "medium", "standard", "mid", "متوسط", "عادي")):
        budget = "moderate"
    elif any(w in text for w in ("econ", "cheap", "low budget", "tight budget", "on a budget", "backpack",
                                 "اقتصاد", "رخيص", "محدود")):
        budget = "economy"

    # Family/group before couple, and no bare digits: "2 days" is not two travellers.
    travelers = None
    if any(w in text for w in ("fam", "kid", "child", "عائل", "أولاد", "الأسرة")):
        travelers = "family"
    elif any(w in text for w in ("group", "friends", "مجموع", "أصدقاء", "اصدقاء", "صحاب", "أصحاب", "اصحاب", "شلة")):
        travelers = "group"
    elif any(w in text for w in ("couple", "my wife", "my husband", "partner", "honeymoon", "زوجان", "زوجين",
                                 "مراتي", "جوزي", "شهر العسل")):
        travelers = "couple"
    elif any(w in text for w in ("solo", "alone", "by myself", "لوحدي", "بمفردي")):
        travelers = "solo"

    is_trip = bool(region or unsupported or days) or any(w in text for w in TRIP_WORDS)
    return {
        "task": "plan_trip" if is_trip else "other",
        "language": "ar" if _has_arabic(message) else "en",
        "search_query": " ".join(interests),
        "interests": interests,
        "region": region,
        "unsupported_region": unsupported,
        "days": days,
        "budget": budget,
        "travelers": travelers,
        "travel_date": weekday,
        "visitor_type": visitor,
    }


AR_WEEKDAYS = dict(zip(["mon", "tue", "wed", "thu", "fri", "sat", "sun"], DAYS_AR))


def _write(brief: Dict[str, Any], language: str) -> str:
    """Template wording for the short reply (the trip sheet shows the timetable)."""
    ar = language == "ar"
    days = brief["days"]
    places = [p for d in days for p in d["places"]]
    areas = list(dict.fromkeys((d.get("area_ar") or d["area"]) if ar else d["area"] for d in days))
    n = len(days)
    if ar:
        length = "يوم" if n == 1 else "يومين" if n == 2 else f"{n} أيام"
        text = f"يلا بينا! جهزت لك {length} في {' و'.join(areas)}، هتبدأ بـ{places[0]}" + (
            f" وكمان {places[1]}." if len(places) > 1 else ".")
        if brief.get("some_opening_hours_unconfirmed"):
            text += " بس اتأكد من مواعيد الفتح قبل ما تروح."
    else:
        length = "a day" if n == 1 else f"{n} days"
        text = f"Here's {length} in {' & '.join(areas)}, starting with {places[0]}" + (
            f" and {places[1]}." if len(places) > 1 else ".")
        if brief.get("some_opening_hours_unconfirmed"):
            text += " Check opening hours before you go."
    return text


def demo_llm(prompt: str, system: Optional[str] = None, json_mode: bool = False) -> Dict[str, Any]:
    if json_mode:
        return {"ok": True, "text": json.dumps(_extract(prompt), ensure_ascii=False), "model": "demo"}
    data = json.loads(prompt.split("DATA:\n", 1)[1])
    language = "ar" if "Egyptian colloquial Arabic" in prompt else "en"
    return {"ok": True, "text": _write(data, language), "model": "demo"}


def demo_search(query: str, region: Optional[str] = None, category: Optional[str] = None,
                max_duration: Optional[float] = None, top_k: int = 5) -> List[Dict[str, Any]]:
    """Keyword overlap instead of embeddings. Same output shape as rag.retriever."""
    words = set(re.findall(r"[a-z]+", query.lower())) - {"top", "attractions", "in", "egypt", "and", "the"}
    words |= {w.rstrip("s") for w in words}
    scored = []
    for a in load_attractions().values():
        if region and a.region != region:
            continue
        if category and a.category != category:
            continue
        if max_duration is not None and a.duration_min / 60 > max_duration:
            continue
        doc = f"{a.name} {a.category} {a.description}".lower()
        overlap = sum(1 for w in words if w and w in doc)
        scored.append((1.5 - 0.15 * overlap + a.id * 0.001, a))
    scored.sort(key=lambda pair: pair[0])
    return [{"content": a.description, "metadata": {"id": a.id, "name": a.name, "region": a.region},
             "relevance_score": score} for score, a in scored[:top_k]]
