from pydantic import BaseModel


class LocationCreate(BaseModel):
    latitude: float
    longitude: float
    district: str
    state: str
    place_name: str
    location_type: str
    score: int = 0


class LocationResponse(BaseModel):
    id: int
    latitude: float
    longitude: float
    district: str
    state: str
    place_name: str
    location_type: str
    score: int

    class Config:
        from_attributes = True


# --- Check-in schemas ---


class Coordinate(BaseModel):
    lat: float
    lon: float


class CheckInRequest(BaseModel):
    user_id: str
    coordinates: list[Coordinate]


class ScoreItem(BaseModel):
    lat: float
    lon: float
    name: str
    score: int
    earned_score: int
    reason: str | None = None


class CheckInResponse(BaseModel):
    user_id: str
    scores: list[ScoreItem]
