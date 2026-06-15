from geoalchemy2 import Geography
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    coordinates = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    district: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(255))
    place_name: Mapped[str] = mapped_column(String(255))
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
