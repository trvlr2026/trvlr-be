from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Visit
from app.schemas import CheckInRequest, CheckInResponse, ScoreItem

router = APIRouter(prefix="/checkin", tags=["checkin"])


@router.post("/", response_model=CheckInResponse)
async def checkin(
    payload: CheckInRequest,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    For each coordinate, find a location within 100m.
    Award score on first visit, return reason if already visited.
    Also updates user_scores with the total earned.
    """
    user_id = payload.user_id
    scores: list[ScoreItem] = []
    total_earned = 0
    processed_locations = set()

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
                    1000
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

        if location_id in processed_locations:
            continue

        processed_locations.add(location_id)

        # Check if user already collected this score
        existing_visit = db.execute(
            text("""
                SELECT id FROM visits
                WHERE user_id = :user_id AND location_id = :location_id
            """),
            {"user_id": user_id, "location_id": location_id},
        ).fetchone()

        if existing_visit:
            # Already visited
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
                user_id=user_id,
                location_id=location_id,
                photo_id=coord.photo_id,
                score=location_score,
            )
            db.add(visit)
            total_earned += location_score

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

    # Update user_scores with total earned this session
    if total_earned > 0:
        db.execute(
            text("""
                INSERT INTO user_scores (user_id, score)
                VALUES (:user_id, :score)
                ON CONFLICT (user_id)
                DO UPDATE SET score = user_scores.score + :score
            """),
            {"user_id": user_id, "score": total_earned},
        )

    db.commit()

    return CheckInResponse(user_id=user_id, scores=scores)
