"""Database models and helpers (SQLAlchemy 2.0).

Three tables:

* ``streams``    — one row per watched YouTube stream.
* ``plates``     — one row per unique plate string (aggregated counts).
* ``detections`` — one row per logged sighting, with timestamp + screenshots.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


def utcnow() -> datetime:
    """Timezone-aware UTC now (stored naive-UTC for SQLite friendliness)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(512), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    detections: Mapped[list["Detection"]] = relationship(back_populates="stream")


class Plate(Base):
    __tablename__ = "plates"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sightings: Mapped[int] = mapped_column(Integer, default=0)

    detections: Mapped[list["Detection"]] = relationship(back_populates="plate")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate_id: Mapped[int] = mapped_column(ForeignKey("plates.id"), index=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("streams.id"), index=True)

    plate_number: Mapped[str] = mapped_column(String(32), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    count: Mapped[int] = mapped_column(Integer, default=1)

    frame_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    plate_crop_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Vehicle attributes (populated when the vehicle detector is enabled).
    vehicle_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vehicle_color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    vehicle_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Make/model + rich taxonomy (Phase 0 columns; populated once models land).
    vehicle_make: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vehicle_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vehicle_make_model_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    vehicle_category: Mapped[str | None] = mapped_column(String(48), nullable=True)
    vehicle_category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    plate: Mapped["Plate"] = relationship(back_populates="detections")
    stream: Mapped["Stream"] = relationship(back_populates="detections")


class Watchlist(Base):
    """Plates of interest. A match triggers an alert when seen."""

    __tablename__ = "watchlist"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Alert(Base):
    """A fired alert for a watchlisted plate sighting."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    plate_number: Mapped[str] = mapped_column(String(32), index=True)
    detection_id: Mapped[int | None] = mapped_column(
        ForeignKey("detections.id"), nullable=True, index=True
    )
    stream_id: Mapped[int | None] = mapped_column(
        ForeignKey("streams.id"), nullable=True
    )
    message: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)


def make_engine(database_url: str):
    """Create an engine, ensuring SQLite parent directories exist."""
    if database_url.startswith("sqlite:///"):
        from pathlib import Path

        db_path = database_url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False so per-stream worker threads can share the engine.
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def init_db(database_url: str):
    """Create tables (if needed) and return a configured session factory."""
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def get_or_create_stream(session, name: str, url: str) -> Stream:
    """Fetch the Stream row for ``url`` or create it."""
    stream = session.query(Stream).filter_by(url=url).one_or_none()
    if stream is None:
        stream = Stream(name=name, url=url)
        session.add(stream)
        session.commit()
    return stream
