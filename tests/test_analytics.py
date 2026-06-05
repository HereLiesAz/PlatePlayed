"""Tests for the analytics queries (in-memory SQLite, no ML/network)."""

from datetime import datetime

import pytest

from plateplayed import analytics
from plateplayed.db import Detection, Plate, Stream, init_db


@pytest.fixture
def session():
    factory = init_db("sqlite:///:memory:")
    with factory() as s:
        yield s


def _seed(session):
    s1 = Stream(name="Cam A", url="http://a")
    s2 = Stream(name="Cam B", url="http://b")
    session.add_all([s1, s2])
    session.flush()

    # ABC123 seen on both streams; XYZ on one.
    p1 = Plate(plate_number="ABC123", sightings=3)
    p2 = Plate(plate_number="XYZ999", sightings=1)
    session.add_all([p1, p2])
    session.flush()

    def d(plate, stream, hour, weekday_date):
        return Detection(
            plate_id=plate.id, stream_id=stream.id, plate_number=plate.plate_number,
            confidence=0.9, count=1,
            seen_at=datetime(2026, 1, weekday_date, hour, 0, 0),
            last_seen_at=datetime(2026, 1, weekday_date, hour, 0, 0),
        )

    session.add_all([
        d(p1, s1, 9, 5),    # Jan 5 2026 is a Monday
        d(p1, s2, 9, 5),
        d(p1, s2, 17, 6),
        d(p2, s1, 17, 6),
    ])
    session.commit()
    return s1, s2


def test_summary_counts(session):
    _seed(session)
    out = analytics.summary(session)
    assert out["streams"] == 2
    assert out["unique_plates"] == 2
    assert out["detections"] == 4
    assert out["watchlist"] == 0


def test_top_plates_ranks_by_sightings_with_stream_count(session):
    _seed(session)
    top = analytics.top_plates(session)
    assert top[0]["plate_number"] == "ABC123"
    assert top[0]["streams"] == 2  # seen on both cams


def test_cross_stream_only_multi_stream_plates(session):
    _seed(session)
    cross = analytics.cross_stream_plates(session)
    assert len(cross) == 1
    assert cross[0]["plate_number"] == "ABC123"
    assert set(cross[0]["stream_names"]) == {"Cam A", "Cam B"}


def test_hourly_histogram_buckets(session):
    _seed(session)
    hours = analytics.hourly_histogram(session)
    assert len(hours) == 24
    assert hours[9] == 2
    assert hours[17] == 2
    assert sum(hours) == 4


def test_weekday_histogram_buckets(session):
    _seed(session)
    days = analytics.weekday_histogram(session)
    assert len(days) == 7
    assert days[0] == 2  # Monday Jan 5
    assert days[1] == 2  # Tuesday Jan 6


def test_volume_by_stream(session):
    s1, _ = _seed(session)
    vol = {v["name"]: v["detections"] for v in analytics.volume_by_stream(session)}
    assert vol == {"Cam A": 2, "Cam B": 2}
