from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Visit
from app.schemas import CheckInRequest, CheckInResponse, ScoreItem

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.post("/", response_model=CheckInResponse)
async def checkin(payload: CheckInRequest, db: Session = Depends(get_db)):
    """
    For each coordinate, find a location within 100m.
    Award score on first visit, return reason if already visited.
    """
    scores: list[ScoreItem] = []

    for coord in payload.coordinates:
        # Find the closest location within 100 meters
        result = db.execute(
            text("""
                SELECT id, place_name, score,
                       ST_Y(coordinates::geometry) as lat,
                       ST_X(coordinates::geometry) as lon
                FROM locations
                WHERE ST_DWithin(
                    coordinates,
                    ST_MakePoint(:lon, :lat)::geography,
                    100
                )
                ORDER BY ST_Distance(coordinates, ST_MakePoint(:lon, :lat)::geography)
                LIMIT 1
            """),
            {"lat": coord.lat, "lon": coord.lon},
        ).fetchone()

        if not result:
            continue

        location_id = result.id
        place_name = result.place_name
        location_score = result.score
        location_lat = result.lat
        location_lon = result.lon

        # Check if user already collected this score
        existing_visit = db.execute(
            text("""
                SELECT id FROM visits
                WHERE user_id = :user_id AND location_id = :location_id
            """),
            {"user_id": payload.user_id, "location_id": location_id},
        ).fetchone()

        if existing_visit:
            # Already visited — return with earned_score=0 and reason
            scores.append(
                ScoreItem(
                    lat=location_lat,
                    lon=location_lon,
                    name=place_name,
                    score=location_score,
                    earned_score=0,
                    reason="ALREADY_VISITED",
                )
            )
        else:
            # First visit — award score and record visit
            visit = Visit(
                user_id=payload.user_id,
                location_id=location_id,
                score=location_score,
            )
            db.add(visit)

            scores.append(
                ScoreItem(
                    lat=location_lat,
                    lon=location_lon,
                    name=place_name,
                    score=location_score,
                    earned_score=location_score,
                    reason=None,
                )
            )

    db.commit()

    return CheckInResponse(user_id=payload.user_id, scores=scores)
