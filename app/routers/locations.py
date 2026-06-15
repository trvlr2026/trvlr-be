from geoalchemy2.functions import ST_X, ST_Y
from geoalchemy2.shape import to_shape
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Location
from app.schemas import LocationCreate, LocationResponse

router = APIRouter(prefix="/locations", tags=["locations"])


@router.post("/", response_model=LocationResponse, status_code=201)
async def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    location = Location(
        coordinates=f"SRID=4326;POINT({payload.longitude} {payload.latitude})",
        district=payload.district,
        state=payload.state,
        place_name=payload.place_name,
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
        score=location.score,
    )
