from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.schemas import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/", response_model=LeaderboardResponse)
async def get_leaderboard(
    state: str | None = Query(None),
    district: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return leaderboard sorted by score descending with pagination.
    Optional state/district filters aggregate from visits + locations.
    """
    offset = (page - 1) * page_size

    if state or district:
        conditions = []
        params: dict = {"limit": page_size, "offset": offset}

        if state:
            conditions.append("l.state = :state")
            params["state"] = state
        if district:
            conditions.append("l.district = :district")
            params["district"] = district

        where_clause = "WHERE " + " AND ".join(conditions)

        results = db.execute(
            text(f"""
                SELECT v.user_id, u.display_name as user_name, SUM(v.score) as score
                FROM visits v
                JOIN locations l ON l.id = v.location_id
                LEFT JOIN users u ON u.id = v.user_id
                {where_clause}
                GROUP BY v.user_id, u.display_name
                ORDER BY score DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).fetchall()
    else:
        results = db.execute(
            text("""
                SELECT us.user_id, u.display_name as user_name, us.score
                FROM user_scores us
                LEFT JOIN users u ON u.id = us.user_id
                ORDER BY us.score DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": page_size, "offset": offset},
        ).fetchall()

    entries = [
        LeaderboardEntry(user_id=row.user_id, user_name=row.user_name or "", score=row.score)
        for row in results
    ]

    return LeaderboardResponse(page=page, page_size=page_size, results=entries)
