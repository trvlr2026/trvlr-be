from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/", response_model=LeaderboardResponse)
async def get_leaderboard(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Return leaderboard sorted by score descending with pagination.
    """
    offset = (page - 1) * page_size

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
