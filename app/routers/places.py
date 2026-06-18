from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.schemas import PlacesTreeResponse, StateNode

router = APIRouter(tags=["places"])


@router.get("/places-tree", response_model=PlacesTreeResponse)
async def get_places_tree(
    current_user: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Return a tree of state -> districts from the places table.
    """
    results = db.execute(
        text("SELECT state, district FROM places ORDER BY state, district")
    ).fetchall()

    tree: dict[str, list[str]] = defaultdict(list)
    for row in results:
        tree[row.state].append(row.district)

    states = [
        StateNode(state=state, districts=districts)
        for state, districts in sorted(tree.items())
    ]

    return PlacesTreeResponse(states=states)
