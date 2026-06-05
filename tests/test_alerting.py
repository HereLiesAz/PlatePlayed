"""Tests for watchlist management and throttled alerting."""

import pytest

from plateplayed.alerting import Alerter, add_watch, list_watch, remove_watch
from plateplayed.db import Alert, Detection, Plate, Stream, init_db


class _CapturingNotifier:
    def __init__(self):
        self.payloads = []

    def notify(self, payload):
        self.payloads.append(payload)
        return True


@pytest.fixture
def factory():
    return init_db("sqlite:///:memory:")


def _make_detection(factory, plate="ABC123"):
    with factory() as s:
        stream = Stream(name="Cam", url="http://c")
        s.add(stream)
        s.flush()
        p = Plate(plate_number=plate, sightings=1)
        s.add(p)
        s.flush()
        det = Detection(
            plate_id=p.id, stream_id=stream.id, plate_number=plate,
            confidence=0.9, count=1,
        )
        s.add(det)
        s.commit()
        return det.id


def test_add_normalizes_and_lists(factory):
    with factory() as s:
        add_watch(s, " abc123 ", note="suspect")
        watch = list_watch(s)
        assert len(watch) == 1
        assert watch[0].plate_number == "ABC123"
        assert watch[0].note == "suspect"


def test_remove_deactivates(factory):
    with factory() as s:
        add_watch(s, "ABC123")
        assert remove_watch(s, "abc123") is True   # case-insensitive match
        assert list_watch(s) == []                 # no longer active
        assert remove_watch(s, "NOTTHERE") is False


def test_alert_fires_for_watched_plate(factory):
    det_id = _make_detection(factory)
    with factory() as s:
        add_watch(s, "ABC123", note="wanted")
    notifier = _CapturingNotifier()
    alerter = Alerter(factory, notifier, cooldown_seconds=300)

    alert = alerter.process(det_id)
    assert alert is not None
    assert alert.delivered is True
    assert len(notifier.payloads) == 1
    assert notifier.payloads[0]["plate_number"] == "ABC123"


def test_no_alert_for_unwatched_plate(factory):
    det_id = _make_detection(factory)
    notifier = _CapturingNotifier()
    alerter = Alerter(factory, notifier, cooldown_seconds=300)
    assert alerter.process(det_id) is None
    assert notifier.payloads == []


def test_cooldown_throttles_repeat_alerts(factory):
    det_id = _make_detection(factory)
    with factory() as s:
        add_watch(s, "ABC123")
    notifier = _CapturingNotifier()
    alerter = Alerter(factory, notifier, cooldown_seconds=300)

    assert alerter.process(det_id) is not None
    assert alerter.process(det_id) is None  # within cooldown
    assert len(notifier.payloads) == 1
    with factory() as s:
        assert s.query(Alert).count() == 1


def test_cooldown_zero_allows_repeat(factory):
    det_id = _make_detection(factory)
    with factory() as s:
        add_watch(s, "ABC123")
    notifier = _CapturingNotifier()
    alerter = Alerter(factory, notifier, cooldown_seconds=0)
    assert alerter.process(det_id) is not None
    assert alerter.process(det_id) is not None
    assert len(notifier.payloads) == 2
