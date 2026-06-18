from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.schemas import ProfileResponse, StateScore

router = APIRouter(tags=["profile"])


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_profile(
    user_id: str,
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return user profile with aggregated stats.
    """
    # Get user info
    user = db.execute(
        text("SELECT display_name, email FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    ).fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get total score
    score_row = db.execute(
        text("SELECT score FROM user_scores WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).fetchone()
    total_score = score_row.score if score_row else 0

    # Get total places visited count
    count_row = db.execute(
        text("SELECT COUNT(*) as count FROM visits WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).fetchone()
    total_places_visited_count = count_row.count if count_row else 0

    # Get points by state
    state_scores = db.execute(
        text("""
            SELECT l.state, SUM(v.score) as score
            FROM visits v
            JOIN locations l ON l.id = v.location_id
            WHERE v.user_id = :user_id
            GROUP BY l.state
            ORDER BY score DESC
        """),
        {"user_id": user_id},
    ).fetchall()

    points_by_state = [
        StateScore(state=row.state, score=row.score)
        for row in state_scores
    ]

    return ProfileResponse(
        user_name=user.display_name,
        user_email=user.email,
        total_score=total_score,
        total_places_visited_count=total_places_visited_count,
        points_by_state=points_by_state,
    )
