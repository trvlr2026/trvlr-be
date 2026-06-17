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
    photo_id: str


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


# --- Nearby locations schemas ---


class NearbyLocationItem(BaseModel):
    id: int
    lat: float
    lon: float
    place_name: str
    district: str
    location_type: str
    score: int
    distance_m: float
    visited: bool


class NearbyResponse(BaseModel):
    user_id: str
    locations: list[NearbyLocationItem]


# --- Leaderboard schemas ---


class LeaderboardEntry(BaseModel):
    user_id: str
    score: int


class LeaderboardResponse(BaseModel):
    page: int
    page_size: int
    results: list[LeaderboardEntry]


# --- User visits schemas ---


class VisitItem(BaseModel):
    location_id: int
    place_name: str
    district: str
    location_type: str
    lat: float
    lon: float
    photo_id: str
    score: int
    visited_at: str


class UserVisitsResponse(BaseModel):
    user_id: str
    page: int
    page_size: int
    results: list[VisitItem]
