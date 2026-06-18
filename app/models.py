from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import Integer, String, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    coordinates = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    district: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(255))
    place_name: Mapped[str] = mapped_column(String(255), unique=True)
    location_type: Mapped[str] = mapped_column(String(100))
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Visit(Base):
    __tablename__ = "visits"
    __table_args__ = (
        UniqueConstraint("user_id", "location_id", name="unique_user_location"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), nullable=False)
    photo_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default="now()")
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class UserScore(Base):
    __tablename__ = "user_scores"

    user_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    district: Mapped[str] = mapped_column(String(255), unique=True)
    state: Mapped[str] = mapped_column(String(255))


import uuid


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, server_default="now()")


class AuthProvider(Base):
    __tablename__ = "auth_providers"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="unique_provider_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "local", "google", "apple"
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)  # email for local, sub for google/apple
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # only for local
