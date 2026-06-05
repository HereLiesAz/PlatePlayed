"""Tests for the recorder's persistence and de-duplication logic.

These run entirely on in-memory SQLite with no ML or network involved.
"""

import numpy as np
import pytest

from plateplayed.db import Detection, Plate, init_db
from plateplayed.detector import PlateDetection
from plateplayed.recorder import Recorder
from plateplayed.storage import ScreenshotStore


@pytest.fixture
def recorder(tmp_path):
    session_factory = init_db("sqlite:///:memory:")
    store = ScreenshotStore(tmp_path / "shots")
    return Recorder(
        session_factory,
        store,
        min_confidence=0.5,
        dedup_cooldown_seconds=30,
        save_plate_crops=False,
    )


def det(text="ABC123", conf=0.9):
    return PlateDetection(text=text, confidence=conf, box=(0, 0, 10, 10))


def test_first_detection_creates_rows(recorder):
    row = recorder.record("Cam 1", "http://s/1", det(), frame=None)
    assert row is not None
    assert row.plate_number == "ABC123"
    assert row.count == 1

    with recorder._Session() as s:
        assert s.query(Plate).count() == 1
        assert s.query(Detection).count() == 1


def test_low_confidence_is_dropped(recorder):
    row = recorder.record("Cam 1", "http://s/1", det(conf=0.1), frame=None)
    assert row is None
    with recorder._Session() as s:
        assert s.query(Detection).count() == 0


def test_repeat_within_cooldown_updates_not_duplicates(recorder):
    first = recorder.record("Cam 1", "http://s/1", det(), frame=None)
    second = recorder.record("Cam 1", "http://s/1", det(), frame=None)

    assert first.id == second.id
    assert second.count == 2
    with recorder._Session() as s:
        assert s.query(Detection).count() == 1
        plate = s.query(Plate).one()
        assert plate.sightings == 2


def test_same_plate_different_stream_is_new_row(recorder):
    recorder.record("Cam 1", "http://s/1", det(), frame=None)
    recorder.record("Cam 2", "http://s/2", det(), frame=None)
    with recorder._Session() as s:
        assert s.query(Detection).count() == 2
        assert s.query(Plate).count() == 1  # same plate, aggregated


def test_cooldown_expiry_creates_new_detection(recorder):
    recorder.cooldown = __import__("datetime").timedelta(seconds=0)
    recorder.record("Cam 1", "http://s/1", det(), frame=None)
    recorder.record("Cam 1", "http://s/1", det(), frame=None)
    with recorder._Session() as s:
        assert s.query(Detection).count() == 2


def test_higher_confidence_updates_on_repeat(recorder):
    recorder.record("Cam 1", "http://s/1", det(conf=0.6), frame=None)
    row = recorder.record("Cam 1", "http://s/1", det(conf=0.95), frame=None)
    assert row.confidence == pytest.approx(0.95)


def test_frame_is_saved_when_provided(recorder):
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    row = recorder.record("Cam 1", "http://s/1", det(), frame=frame)
    assert row.frame_path is not None
    import os
    assert os.path.exists(row.frame_path)
