from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/", response_model=LeaderboardResponse)
async def get_leaderboard(
    state: str | None = Query(None),
    district: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Return leaderboard sorted by score descending with pagination.
    Optional state/district filters aggregate from visits + locations.
    """
    offset = (page - 1) * page_size

    if state or district:
        # Filtered leaderboard: aggregate from visits joined with locations
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
                SELECT v.user_id, SUM(v.score) as score
                FROM visits v
                JOIN locations l ON l.id = v.location_id
                {where_clause}
                GROUP BY v.user_id
                ORDER BY score DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        ).fetchall()
    else:
        # Global leaderboard from user_scores table
        results = db.execute(
            text("""
                SELECT user_id, score
                FROM user_scores
                ORDER BY score DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": page_size, "offset": offset},
        ).fetchall()

    entries = [
        LeaderboardEntry(user_id=row.user_id, score=row.score)
        for row in results
    ]

    return LeaderboardResponse(page=page, page_size=page_size, results=entries)
