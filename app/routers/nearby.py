from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.schemas import NearbyLocationItem, NearbyResponse

router = APIRouter(prefix="/nearby", tags=["nearby"])


@router.get("/", response_model=NearbyResponse)
async def nearby_locations(
    user_id: str = Query(...),
    lat: float = Query(...),
    lon: float = Query(...),
    radius: float = Query(..., description="Radius in metres"),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return all locations within the given radius, with a visited marker per user.
    """
    results = db.execute(
        text("""
            SELECT
                l.id,
                l.place_name,
                l.district,
                l.location_type,
                l.score,
                ST_Y(l.coordinates::geometry) as lat,
                ST_X(l.coordinates::geometry) as lon,
                ST_Distance(l.coordinates, ST_MakePoint(:lon, :lat)::geography) as distance_m,
                CASE WHEN v.id IS NOT NULL THEN true ELSE false END as visited
            FROM locations l
            LEFT JOIN visits v ON v.location_id = l.id AND v.user_id = :user_id
            WHERE ST_DWithin(
                l.coordinates,
                ST_MakePoint(:lon, :lat)::geography,
                :radius
            )
            ORDER BY distance_m
        """),
        {"lat": lat, "lon": lon, "radius": radius, "user_id": user_id},
    ).fetchall()

    locations = [
        NearbyLocationItem(
            id=row.id,
            lat=row.lat,
            lon=row.lon,
            place_name=row.place_name,
            district=row.district,
            location_type=row.location_type,
            score=row.score,
            distance_m=round(row.distance_m, 2),
            visited=row.visited,
        )
        for row in results
    ]

    return NearbyResponse(user_id=user_id, locations=locations)
