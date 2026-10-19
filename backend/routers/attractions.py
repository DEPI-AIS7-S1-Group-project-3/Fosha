from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from agents.hours import check_opening_hours
from backend.config import Settings
from backend.dependencies import get_settings_dep
from backend.errors import bad_request, not_found
from backend.schemas import AttractionDetail, AttractionList, OpeningCheck
from backend.services import attractions as data

router = APIRouter(tags=["attractions"])


@router.get("/attractions", response_model=AttractionList)
def list_attractions(
    region: Optional[str] = Query(None, description='e.g. "Luxor". "Cairo" also includes Giza.'),
    category: Optional[str] = Query(None, description='e.g. "Museum"'),
    q: Optional[str] = Query(None, max_length=100, description="Text search in name and description"),
) -> dict:
    if region and region.strip().lower() not in {r.lower() for r in data.regions()} | {"greater cairo"}:
        raise bad_request(f"Unknown region {region!r}. Valid: {data.regions()}")
    if category and category.strip().lower() not in {c.lower() for c in data.categories()}:
        raise bad_request(f"Unknown category {category!r}. Valid: {data.categories()}")
    items = data.list_attractions(region, category, q)
    return {"total": len(items), "items": [data.summary(a) for a in items]}


@router.get("/attractions/{attraction_id}", response_model=AttractionDetail)
def get_attraction(attraction_id: int, settings: Settings = Depends(get_settings_dep)) -> dict:
    attraction = data.find(attraction_id)
    if attraction is None:
        raise not_found(f"No attraction with id {attraction_id}")
    return data.detail(attraction, settings.stale_after_days)


@router.get("/attractions/{attraction_id}/opening", response_model=OpeningCheck)
def check_opening(
    attraction_id: int,
    day: str = Query(..., description='Weekday name ("Friday") or date (YYYY-MM-DD)'),
    start: str = Query("09:00", pattern=r"^\d{2}:\d{2}$"),
    duration_min: Optional[int] = Query(None, ge=1, le=24 * 60),
) -> dict:
    """Is this place open for a visit starting at `start` on `day`?"""
    if data.find(attraction_id) is None:
        raise not_found(f"No attraction with id {attraction_id}")
    result = check_opening_hours(attraction_id, day, start, duration_min)
    if not result["ok"]:
        raise bad_request(result["error"])
    return {"attraction_id": attraction_id, "day": day, "start": start, **result}


@router.get("/regions", response_model=List[str])
def list_regions() -> List[str]:
    return data.regions()


@router.get("/categories", response_model=List[str])
def list_categories() -> List[str]:
    return data.categories()
