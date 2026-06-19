from geoalchemy2.shape import to_shape
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Location
from app.schemas import LocationCreate, LocationListResponse, LocationResponse


def parse_wkt_polygon(wkt: str | None) -> list[list[float]] | None:
    """Parse WKT POLYGON string to list of [lon, lat] pairs."""
    if not wkt or not wkt.startswith("POLYGON"):
        return None
    try:
        # Extract coordinates from POLYGON((lon lat, lon lat, ...))
        inner = wkt.replace("POLYGON((", "").replace("))", "")
        coords = []
        for pair in inner.split(","):
            parts = pair.strip().split(" ")
            coords.append([float(parts[0]), float(parts[1])])
        return coords
    except Exception:
        return None

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/", response_model=LocationListResponse)
async def list_locations(
    state: str | None = Query(None),
    district: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return paginated list of locations with optional state/district filters.
    """
    offset = (page - 1) * page_size

    conditions = []
    params: dict = {"limit": page_size, "offset": offset}

    if state:
        conditions.append("state = :state")
        params["state"] = state
    if district:
        conditions.append("district = :district")
        params["district"] = district

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    results = db.execute(
        text(f"""
            SELECT id, place_name, district, state, location_type, radius_m, score,
                   ST_Y(coordinates::geometry) as lat,
                   ST_X(coordinates::geometry) as lon,
                   ST_AsText(boundary::geometry) as boundary_wkt
            FROM locations
            {where_clause}
            ORDER BY score DESC
            LIMIT :limit OFFSET :offset
        """),
        params,
    ).fetchall()

    items = [
        LocationResponse(
            id=row.id,
            latitude=row.lat,
            longitude=row.lon,
            district=row.district,
            state=row.state,
            place_name=row.place_name,
            location_type=row.location_type,
            radius_m=row.radius_m or 100,
            boundary=parse_wkt_polygon(row.boundary_wkt),
            score=row.score,
        )
        for row in results
    ]

    return LocationListResponse(page=page, page_size=page_size, results=items)


@router.post("/", response_model=LocationResponse, status_code=201)
async def create_location(
    payload: LocationCreate,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    location = Location(
        coordinates=f"SRID=4326;POINT({payload.longitude} {payload.latitude})",
        district=payload.district,
        state=payload.state,
        place_name=payload.place_name,
        location_type=payload.location_type,
        score=payload.score,
    )
    db.add(location)
    db.commit()
    db.refresh(location)

    point = to_shape(location.coordinates)
    return LocationResponse(
        id=location.id,
        latitude=point.y,
        longitude=point.x,
        district=location.district,
        state=location.state,
        place_name=location.place_name,
        location_type=location.location_type,
        radius_m=location.radius_m or 100,
        boundary=None,
        score=location.score,
    )
