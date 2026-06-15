from pydantic import BaseModel


class LocationCreate(BaseModel):
    latitude: float
    longitude: float
    district: str
    state: str
    place_name: str
    score: int = 0


class LocationResponse(BaseModel):
    id: int
    latitude: float
    longitude: float
    district: str
    state: str
    place_name: str
    score: int

    class Config:
        from_attributes = True
