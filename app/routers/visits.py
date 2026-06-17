from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UserVisitsResponse, VisitItem

router = APIRouter(tags=["visits"])


@router.get("/{user_id}/visits", response_model=UserVisitsResponse)
async def get_user_visits(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Return paginated list of all visits by a user with location details.
    """
    offset = (page - 1) * page_size

    results = db.execute(
        text("""
            SELECT
                v.location_id,
                l.place_name,
                l.district,
                l.location_type,
                ST_Y(l.coordinates::geometry) as lat,
                ST_X(l.coordinates::geometry) as lon,
                v.photo_id,
                v.score,
                v.created_at
            FROM visits v
            JOIN locations l ON l.id = v.location_id
            WHERE v.user_id = :user_id
            ORDER BY v.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"user_id": user_id, "limit": page_size, "offset": offset},
    ).fetchall()

    items = [
        VisitItem(
            location_id=row.location_id,
            place_name=row.place_name,
            district=row.district,
            location_type=row.location_type,
            lat=row.lat,
            lon=row.lon,
            photo_id=row.photo_id or "",
            score=row.score,
            visited_at=row.created_at.isoformat() if row.created_at else "",
        )
        for row in results
    ]

    return UserVisitsResponse(
        user_id=user_id,
        page=page,
        page_size=page_size,
        results=items,
    )
