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


class LocationListResponse(BaseModel):
    page: int
    page_size: int
    results: list[LocationResponse]


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
    user_name: str
    score: int


class LeaderboardResponse(BaseModel):
    page: int
    page_size: int
    results: list[LeaderboardEntry]


# --- User visits schemas ---


class VisitLocationItem(BaseModel):
    id: int
    lat: float
    lon: float
    place_name: str
    district: str
    location_type: str
    score: int


class VisitItem(BaseModel):
    photo_id: str
    score: int
    visited_at: str
    location: VisitLocationItem


class UserVisitsResponse(BaseModel):
    user_id: str
    page: int
    page_size: int
    results: list[VisitItem]


# --- Places tree schemas ---


class StateNode(BaseModel):
    state: str
    districts: list[str]


class PlacesTreeResponse(BaseModel):
    states: list[StateNode]


# --- Profile schemas ---


class StateScore(BaseModel):
    state: str
    score: int


class ProfileResponse(BaseModel):
    user_name: str
    user_email: str | None
    total_score: int
    total_places_visited_count: int
    points_by_state: list[StateScore]
