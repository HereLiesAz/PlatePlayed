"""Read-only analytics over logged detections.

Plain functions taking a SQLAlchemy session and returning JSON-friendly dicts,
so they can be unit-tested against an in-memory database. Time-bucketing is done
in Python to stay portable across SQLite and Postgres.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import distinct, func

from .db import Alert, Detection, Plate, Stream, Watchlist, utcnow


def summary(session) -> dict:
    """Top-line counts, including activity in the last 24h."""
    day_ago = utcnow() - timedelta(hours=24)
    return {
        "streams": session.query(func.count(Stream.id)).scalar() or 0,
        "unique_plates": session.query(func.count(Plate.id)).scalar() or 0,
        "detections": session.query(func.count(Detection.id)).scalar() or 0,
        "detections_24h": (
            session.query(func.count(Detection.id))
            .filter(Detection.seen_at >= day_ago)
            .scalar()
            or 0
        ),
        "watchlist": (
            session.query(func.count(Watchlist.id))
            .filter(Watchlist.active.is_(True))
            .scalar()
            or 0
        ),
        "alerts": session.query(func.count(Alert.id)).scalar() or 0,
    }


def top_plates(session, limit: int = 20) -> list[dict]:
    """Most-seen plates, with how many distinct streams each appeared on."""
    rows = (
        session.query(
            Plate.plate_number,
            Plate.sightings,
            Plate.first_seen,
            Plate.last_seen,
            func.count(distinct(Detection.stream_id)).label("streams"),
        )
        .join(Detection, Detection.plate_id == Plate.id)
        .group_by(Plate.id)
        .order_by(Plate.sightings.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "plate_number": r.plate_number,
            "sightings": r.sightings,
            "first_seen": r.first_seen,
            "last_seen": r.last_seen,
            "streams": r.streams,
        }
        for r in rows
    ]


def cross_stream_plates(session, limit: int = 20) -> list[dict]:
    """Plates seen on more than one stream (movement between cameras)."""
    rows = (
        session.query(
            Detection.plate_number,
            func.count(distinct(Detection.stream_id)).label("streams"),
            func.count(Detection.id).label("sightings"),
        )
        .group_by(Detection.plate_number)
        .having(func.count(distinct(Detection.stream_id)) > 1)
        .order_by(func.count(distinct(Detection.stream_id)).desc())
        .limit(limit)
        .all()
    )
    result = []
    for r in rows:
        names = [
            n
            for (n,) in session.query(distinct(Stream.name))
            .join(Detection, Detection.stream_id == Stream.id)
            .filter(Detection.plate_number == r.plate_number)
            .all()
        ]
        result.append(
            {
                "plate_number": r.plate_number,
                "streams": r.streams,
                "sightings": r.sightings,
                "stream_names": names,
            }
        )
    return result


def hourly_histogram(session, stream_id: int | None = None) -> list[int]:
    """24 buckets: detection counts by hour-of-day (UTC)."""
    q = session.query(Detection.seen_at)
    if stream_id is not None:
        q = q.filter(Detection.stream_id == stream_id)
    buckets = [0] * 24
    for (ts,) in q.all():
        if ts is not None:
            buckets[ts.hour] += 1
    return buckets


def weekday_histogram(session, stream_id: int | None = None) -> list[int]:
    """7 buckets (Mon..Sun): detection counts by day-of-week."""
    q = session.query(Detection.seen_at)
    if stream_id is not None:
        q = q.filter(Detection.stream_id == stream_id)
    buckets = [0] * 7
    for (ts,) in q.all():
        if ts is not None:
            buckets[ts.weekday()] += 1
    return buckets


def volume_by_stream(session) -> list[dict]:
    """Per-stream detection totals and most recent sighting."""
    rows = (
        session.query(
            Stream.id,
            Stream.name,
            func.count(Detection.id).label("detections"),
            func.max(Detection.last_seen_at).label("last_seen"),
        )
        .outerjoin(Detection, Detection.stream_id == Stream.id)
        .group_by(Stream.id)
        .order_by(func.count(Detection.id).desc())
        .all()
    )
    return [
        {
            "stream_id": r.id,
            "name": r.name,
            "detections": r.detections,
            "last_seen": r.last_seen,
        }
        for r in rows
    ]
