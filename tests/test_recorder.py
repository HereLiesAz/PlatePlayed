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


def test_concurrent_same_plate_no_integrity_error(tmp_path):
    # Many threads recording the same brand-new plate at once must not race
    # into a duplicate-insert (unique constraint) error; the lock serializes.
    # Uses a file-backed SQLite so all threads share one database (an
    # in-memory DB would give each thread its own copy).
    import threading

    session_factory = init_db(f"sqlite:///{tmp_path / 'race.db'}")
    recorder = Recorder(
        session_factory,
        ScreenshotStore(tmp_path / "shots"),
        min_confidence=0.5,
        dedup_cooldown_seconds=30,
        save_plate_crops=False,
    )

    errors: list[Exception] = []

    def worker():
        try:
            recorder.record("Cam 1", "http://s/1", det(), frame=None)
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    with recorder._Session() as s:
        assert s.query(Plate).count() == 1  # exactly one plate row, no dupes


def test_vehicle_attributes_are_persisted(recorder):
    from plateplayed.vehicle import VehicleInfo

    info = VehicleInfo(type="truck", color="red", confidence=0.88)
    row = recorder.record("Cam 1", "http://s/1", det(), frame=None, vehicle=info)
    assert row.vehicle_type == "truck"
    assert row.vehicle_color == "red"
    assert row.vehicle_confidence == 0.88


def test_vehicle_attributes_backfilled_on_repeat(recorder):
    from plateplayed.vehicle import VehicleInfo

    recorder.record("Cam 1", "http://s/1", det(), frame=None, vehicle=None)
    info = VehicleInfo(type="car", color="blue", confidence=0.7)
    row = recorder.record("Cam 1", "http://s/1", det(), frame=None, vehicle=info)
    assert row.count == 2  # same detection row (within cooldown)
    assert row.vehicle_type == "car"
    assert row.vehicle_color == "blue"


def test_make_model_and_category_persisted(recorder):
    from plateplayed.vehicle import VehicleInfo

    info = VehicleInfo(
        type="car", color="white", confidence=0.9,
        make="Honda", model="Civic", make_model_confidence=0.8,
        category="police", category_confidence=0.75,
    )
    row = recorder.record("Cam 1", "http://s/1", det(), frame=None, vehicle=info)
    assert row.vehicle_make == "Honda"
    assert row.vehicle_model == "Civic"
    assert row.vehicle_category == "police"
    assert row.vehicle_category_confidence == 0.75


def test_frame_is_saved_when_provided(recorder):
    frame = np.zeros((20, 20, 3), dtype=np.uint8)
    row = recorder.record("Cam 1", "http://s/1", det(), frame=frame)
    assert row.frame_path is not None
    # Paths are stored relative to the screenshot root.
    full = recorder._store.root / row.frame_path
    assert full.exists()
