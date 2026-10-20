"""Edit the plan the user already has: "ممكن نحط كنيسة الأنبا بيشوي بعد الفنار",
"remove the museum", "make it 2 days".

The client sends the current plan back with the message (the server keeps no
session). The LLM only decides WHAT to change, and only by referring to ids from
a list of real places in the plan's area; the scheduler then re-times the edited
days with the usual hard rules. A place that no longer fits is reported, not
squeezed in.
"""
import json
from typing import Any, Callable, Dict, List, Optional

from agents.attractions import get_attraction, load_attractions
from agents.places_online import arabic_name, find_places, register_places
from agents.scheduler import area_of, build_itinerary, time_day

LLMFn = Callable[..., Dict[str, Any]]

SYSTEM = (
    "You edit an existing Egypt trip plan. Reply with ONE JSON object and nothing else:\n"
    '  type: "edit" if the user wants to change the current plan (add, remove, reorder places, or change '
    'the number of days); "new_trip" if they ask for a different trip or destination; otherwise "other"\n'
    "  add: list of {id, after_id, day}: places to add, by id from AVAILABLE. after_id = the id of the "
    "stop it should follow if the user said so, else null; day = day number if the user said so, else null\n"
    "  remove: list of ids from PLAN to remove\n"
    "  days: new number of days if the user asked to change it, else null\n"
    "Only use ids that appear in the lists. Match place names in any language or spelling "
    '(e.g. "الفنار" = the lighthouse, "كنيسة الانبا بيشوي" = Saint Bishoy church). '
    "If the user names a place that is not in AVAILABLE, leave it out."
)


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
    pool = [a for a in load_attractions().values() if area_of(a.region) in areas and a.id not in in_plan]

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
    if not removed and not added and not new_days:
        return {"edited": False, "itinerary": None, "summary": {"reason": "no_match"}}

    days = [[i for i in day if i not in removed] for day in days]
    for item in added:
        target = next((n for n, day in enumerate(days) if item["after"] in day), None)
        if target is not None:
            days[target].insert(days[target].index(item["after"]) + 1, item["id"])
        else:
            n = item["day"] - 1 if isinstance(item["day"], int) and 1 <= item["day"] <= len(days) else len(days) - 1
            days[n].append(item["id"])

    first_day = (context.get("intent") or {}).get("travel_date")
    if new_days and new_days != len(days):
        order = [i for day in days for i in day]
        itinerary = build_itinerary(order, new_days, first_day=first_day,
                                    max_stops_per_day=max(2, min(4, -(-len(order) // new_days))))
        dropped = itinerary.get("unscheduled", [])
    else:
        timed = [time_day(day, n, area_of(get_attraction(day[0]).region) if day else "", first_day)
                 for n, day in enumerate(days, start=1)]
        dropped = [d for t in timed for d in t["dropped"]]
        itinerary = {"ok": True, "days": [t["day"] for t in timed if t["day"]["stops"]],
                     "unscheduled": dropped,
                     "warnings": ["Travel times are estimates (no live traffic data)."]}
    return {"edited": True, "itinerary": itinerary,
            "summary": {"added": added, "removed": removed, "days": new_days,
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
    if summary.get("days"):
        n = summary["days"]
        parts.append((f"خليت الرحلة {'يوم' if n == 1 else 'يومين' if n == 2 else f'{n} أيام'}") if ar
                     else f"made it {n} day{'s' if n != 1 else ''}")
    text = ("تمام، " + "، و".join(parts) + ".") if ar else ("Done: " + ", ".join(parts) + ".")
    if summary.get("dropped"):
        names = "، ".join(_label(i, ar) for i in summary["dropped"]) if ar else ", ".join(_label(i, ar) for i in summary["dropped"])
        text += (f" بس {names} مش هيلحق في اليوم (المواعيد أو الوقت مش مكفيين)." if ar
                 else f" {names} no longer fits in the day (opening hours or time).")
    return text + (" البرنامج اتحدّث 👇" if ar else " Your plan is updated 👇")
