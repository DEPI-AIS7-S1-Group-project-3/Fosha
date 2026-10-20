"""Edit the plan the user already has: "ممكن نحط كنيسة الأنبا بيشوي بعد الفنار",
"remove the museum", "make it 2 days".

The client sends the current plan back with the message (the server keeps no
session). The LLM only decides WHAT to change, and only by referring to ids from
a list of real places in the plan's area; the scheduler then re-times the edited
days with the usual hard rules. A place that no longer fits is reported, not
squeezed in.
"""
import json
import re
from typing import Any, Callable, Dict, List, Optional

from agents.attractions import get_attraction, load_attractions
from agents.places_online import arabic_name, find_places, register_places
from agents.scheduler import area_of, build_itinerary, time_day
from agents.travel import haversine_km, load_locations

LLMFn = Callable[..., Dict[str, Any]]

SYSTEM = (
    "You decide whether a message EDITS the user's current Egypt trip plan. Reply with ONE JSON object:\n"
    '  type: "edit" ONLY if the message asks to change THIS plan: add/remove/move a named place, or change '
    'the length of this trip ("make it 3 days"). "new_trip" if it describes a trip (where/how long/with whom) '
    'without asking to change the current one. Otherwise "other".\n'
    "  add: list of {id, after_id, day}: places to add, by id from AVAILABLE; after_id = id of the stop it "
    "should follow if the user said so, else null; day = day number if the user said so, else null\n"
    "  remove: list of ids from PLAN to remove\n"
    "  days: the new number of days ONLY if the user explicitly asked to change the length, else null\n"
    "Only use ids from the lists; match place names in any language or spelling "
    '(e.g. "الفنار" = the lighthouse, "كنيسة الانبا بيشوي" = Saint Bishoy church, "the oracle temple" = '
    "Temple of the Oracle). If a named place isn't in AVAILABLE, leave it out.\n"
    "Examples:\n"
    '  "عايزة اطلع يوم" / "I want a day trip" / "3 days in Luxor" / "عايزة اطلع يوم مع صحابي" -> new_trip\n'
    '  "add the oracle temple" / "ممكن نحط الكنيسة بعد الفنار" / "شيل المتحف" -> edit\n'
    '  "خليها ٣ أيام" / "make it 2 days instead" -> edit with days\n'
)

# Cue words: the model's answer is only trusted when the message actually asks for that change.
ADD_CUES = ("add", "include", "put", "insert", "ضيف", "ضيفي", "زود", "زودي", "حط", "نحط", "حطي", "أضف", "اضف")
REMOVE_CUES = ("remove", "drop", "skip", "delete", "without", "take out", "cut", "شيل", "شيلي", "نشيل", "احذف",
               "الغي", "ألغي", "من غير", "بلاش")
DAYS_CUES = ("make it", "make the trip", "change", "extend", "shorten", "longer", "shorter", "instead",
             "خلي", "خلّي", "خليها", "خليه", "خليهم", "اجعل", "غير", "زود", "قلل", "بدل", "بدال", "يبقى", "تبقى", "بقى")
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "a week": 7,
                "واحد": 1, "يومين": 2, "اتنين": 2, "تلات": 3, "ثلاث": 3, "تلاتة": 3, "ثلاثة": 3, "اربع": 4,
                "أربع": 4, "اربعة": 4, "أربعة": 4, "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6, "اسبوع": 7, "أسبوع": 7}
NEARBY_KM = 40
_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def _has(message: str, cues: tuple) -> bool:
    text = message.lower()
    return any(cue in text for cue in cues)


def _numbers_in(message: str) -> set:
    text = message.lower().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    found = {int(n) for n in re.findall(r"\d+", text)}
    found |= {n for word, n in NUMBER_WORDS.items() if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text)}
    if re.search(r"(?<!\w)(a|one) day(?!s)|(?<!\w)يوم(?!\w)", text):
        found.add(1)
    return found


def _label(attraction_id: int, ar: bool) -> str:
    a = get_attraction(attraction_id)
    return (arabic_name(attraction_id) if ar else None) or (a.name if a else str(attraction_id))


def _ensure_registered(context: Dict[str, Any], llm: LLMFn,
                       places_fn: Optional[Callable[[str], Dict[str, Any]]]) -> None:
    """Places found online live in memory; after a server restart, look the town up again."""
    ids = [i for day in context["days"] for i in day]
    town = (context.get("intent") or {}).get("unsupported_region")
    if town and any(get_attraction(i) is None for i in ids):
        found = (places_fn or (lambda name: find_places(name, llm=llm)))(town)
        if found.get("ok"):
            register_places(found["places"])


def edit_plan(message: str, context: Dict[str, Any], llm: LLMFn,
              places_fn: Optional[Callable[[str], Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """Returns None when the message isn't an edit (the caller plans normally), else
    {"edited": bool, "itinerary": {...} | None, "summary": {...}}."""
    _ensure_registered(context, llm, places_fn)
    days: List[List[int]] = [[i for i in day if get_attraction(i)] for day in context.get("days") or []]
    if not any(days):
        return None
    areas = {area_of(get_attraction(i).region) for day in days for i in day}
    in_plan = {i for day in days for i in day}
    locations = load_locations()
    plan_points = [locations[i] for i in in_plan if i in locations]

    def distance_to_plan(attraction_id: int) -> float:
        loc = locations.get(attraction_id)
        if not loc or not plan_points:
            return float("inf")
        return min(haversine_km(loc["lat"], loc["lon"], p["lat"], p["lon"]) for p in plan_points)

    # Places that could join this trip: same area, or within NEARBY_KM of a stop (e.g. the curated
    # Oracle Temple for a Siwa plan built from Wikivoyage), nearest first.
    pool = sorted((a for a in load_attractions().values() if a.id not in in_plan
                   and (area_of(a.region) in areas or distance_to_plan(a.id) <= NEARBY_KM)),
                  key=lambda a: distance_to_plan(a.id))

    def line(i: int) -> str:
        ar_name = arabic_name(i)
        return f"[{i}] {get_attraction(i).name}" + (f" ({ar_name})" if ar_name else "")

    prompt = ("PLAN:\n" + "\n".join(f"Day {n}: " + " -> ".join(line(i) for i in day)
                                    for n, day in enumerate(days, start=1))
              + "\n\nAVAILABLE:\n" + "\n".join(line(a.id) for a in pool)
              + f"\n\nUSER: {message}")
    result = llm(prompt, system=SYSTEM, json_mode=True)
    try:
        edit = json.loads(result["text"]) if result.get("ok") else {}
    except (ValueError, TypeError):
        return None
    if edit.get("type") != "edit":
        return None

    valid = in_plan | {a.id for a in pool}
    def as_id(value: Any) -> Optional[int]:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
        return value if value in valid else None

    removed = [i for i in (as_id(v) for v in edit.get("remove") or []) if i in in_plan]
    if removed and not _has(message, REMOVE_CUES):
        removed = []      # the model removed something the user never asked to remove
    added = []
    for item in edit.get("add") or []:
        pid = as_id((item or {}).get("id"))
        if pid is None or pid in in_plan:
            continue
        added.append({"id": pid, "after": as_id(item.get("after_id")), "day": item.get("day")})
    try:
        new_days = int(edit["days"]) if edit.get("days") else None
    except (TypeError, ValueError):
        new_days = None
    # A new length counts only if the user asked for a change AND said that number;
    # "عايزة اطلع يوم مع صحابي" is a new trip, not "make this plan N days".
    if new_days and not (1 <= new_days <= 14 and _has(message, DAYS_CUES) and new_days in _numbers_in(message)):
        new_days = None
    if new_days == len(days):
        new_days = None
    if not removed and not added and not new_days:
        if _has(message, ADD_CUES + REMOVE_CUES):
            return {"edited": False, "itinerary": None, "summary": {"reason": "no_match"}}
        return None       # not an edit after all: plan it as a new request

    days = [[i for i in day if i not in removed] for day in days]
    for item in added:
        target = next((n for n, day in enumerate(days) if item["after"] in day), None)
        if target is not None:
            days[target].insert(days[target].index(item["after"]) + 1, item["id"])
        else:
            n = item["day"] - 1 if isinstance(item["day"], int) and 1 <= item["day"] <= len(days) else len(days) - 1
            days[n].append(item["id"])

    first_day = (context.get("intent") or {}).get("travel_date")
    short_of_places = None
    if new_days:
        order = [i for day in days for i in day]
        if new_days > len(days):  # longer trip: offer nearby places to fill the new days
            order += [a.id for a in pool if a.id not in order][:4 * (new_days - len(days))]
        itinerary = build_itinerary(order, new_days, first_day=first_day,
                                    max_stops_per_day=max(2, min(4, -(-len(order) // new_days))))
        itinerary["days"] = [d for d in itinerary.get("days", []) if d["stops"]]
        for n, d in enumerate(itinerary["days"], start=1):
            d["day"] = n
        if len(itinerary["days"]) < new_days:
            short_of_places = len(itinerary["days"])
        # Only places that were in the plan count as dropped; unused suggestions don't.
        dropped = [u for u in itinerary.get("unscheduled", []) if u["attraction_id"] in in_plan]
        itinerary["unscheduled"] = dropped
    else:
        timed = [time_day(day, n, area_of(get_attraction(day[0]).region) if day else "", first_day)
                 for n, day in enumerate(days, start=1)]
        dropped = [d for t in timed for d in t["dropped"]]
        itinerary = {"ok": True, "days": [t["day"] for t in timed if t["day"]["stops"]],
                     "unscheduled": dropped,
                     "warnings": ["Travel times are estimates (no live traffic data)."]}
    return {"edited": True, "itinerary": itinerary,
            "summary": {"added": added, "removed": removed, "days": new_days, "short_of_places": short_of_places,
                        "dropped": [d["attraction_id"] for d in dropped]}}


def describe(summary: Dict[str, Any], language: str) -> str:
    """Instant, factual confirmation of what changed (no model call)."""
    ar = language == "ar"
    if summary.get("reason") == "no_match":
        return ("ملقتش المكان ده في المنطقة اللي في برنامجك. جرّب تكتب الاسم بشكل تاني."
                if ar else "I couldn't find that place in your plan's area. Try another name or spelling.")
    parts = []
    for item in summary.get("added", []):
        name = _label(item["id"], ar)
        if item["after"]:
            parts.append(f"ضفت {name} بعد {_label(item['after'], ar)}" if ar
                         else f"added {name} after {_label(item['after'], ar)}")
        else:
            parts.append(f"ضفت {name}" if ar else f"added {name}")
    for pid in summary.get("removed", []):
        parts.append(f"شيلت {_label(pid, ar)}" if ar else f"removed {_label(pid, ar)}")
    def length(n: int) -> str:
        if ar:
            return "يوم" if n == 1 else "يومين" if n == 2 else f"{str(n).translate(_AR_DIGITS)} أيام"
        return f"{n} day{'s' if n != 1 else ''}"

    if summary.get("days"):
        parts.append(f"خليت الرحلة {length(summary['days'])}" if ar else f"made it {length(summary['days'])}")
    text = ("تمام، " + "، و".join(parts) + ".") if ar else ("Done: " + ", ".join(parts) + ".")
    if summary.get("short_of_places"):
        n = summary["short_of_places"]
        text += (f" بس الأماكن اللي تنفع في المنطقة دي تكفي {length(n)} بس." if ar
                 else f" There are only enough places nearby for {length(n)}.")
    if summary.get("dropped"):
        names = "، ".join(_label(i, ar) for i in summary["dropped"]) if ar else ", ".join(_label(i, ar) for i in summary["dropped"])
        text += (f" بس {names} مش هيلحق في اليوم (المواعيد أو الوقت مش مكفيين)." if ar
                 else f" {names} no longer fits in the day (opening hours or time).")
    return text + (" البرنامج اتحدّث 👇" if ar else " Your plan is updated 👇")
