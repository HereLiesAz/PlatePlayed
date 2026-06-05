"""Tests for multi-frame tracking and best-read voting."""

from plateplayed.detector import PlateDetection
from plateplayed.tracking import PlateTracker, iou


def det(text="ABC123", conf=0.9, box=(100, 100, 200, 140)):
    return PlateDetection(text=text, confidence=conf, box=box)


def test_iou_basics():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert 0.0 < iou((0, 0, 10, 10), (5, 0, 15, 10)) < 1.0


def test_min_hits_suppresses_one_frame_false_positive():
    tr = PlateTracker(min_hits=2)
    assert tr.update([det()], now=0.0) == []          # first frame: nothing
    out = tr.update([det()], now=0.5)                 # second frame: emitted
    assert len(out) == 1
    assert out[0].text == "ABC123"


def test_best_read_voting_picks_majority():
    tr = PlateTracker(min_hits=1)
    tr.update([det(text="ABC123", conf=0.7)], now=0.0)
    tr.update([det(text="ABCl23", conf=0.95)], now=0.3)  # higher conf, wrong text
    out = tr.update([det(text="ABC123", conf=0.6)], now=0.6)
    # ABC123 has 2 votes vs 1 — wins despite the lower-confidence reads.
    assert out[0].text == "ABC123"


def test_consensus_uses_best_confidence_crop_of_winner():
    tr = PlateTracker(min_hits=1)
    tr.update([det(text="ABC123", conf=0.6, box=(0, 0, 10, 10))], now=0.0)
    out = tr.update([det(text="ABC123", conf=0.92, box=(1, 1, 11, 11))], now=0.3)
    assert out[0].confidence == 0.92
    assert out[0].box == (1, 1, 11, 11)


def test_distinct_boxes_create_separate_tracks():
    tr = PlateTracker(min_hits=1)
    out = tr.update(
        [det(text="AAA111", box=(0, 0, 50, 30)), det(text="BBB222", box=(400, 300, 460, 340))],
        now=0.0,
    )
    assert {o.text for o in out} == {"AAA111", "BBB222"}


def test_moving_box_stays_one_track():
    tr = PlateTracker(min_hits=2, iou_threshold=0.2)
    tr.update([det(box=(100, 100, 200, 140))], now=0.0)
    out = tr.update([det(box=(110, 105, 210, 145))], now=0.3)  # shifted but overlapping
    assert len(out) == 1  # same track, not a new one


def test_expired_track_is_dropped():
    tr = PlateTracker(min_hits=1, max_age_seconds=1.0)
    tr.update([det()], now=0.0)
    # Long gap → old track expires; this is effectively a fresh first sighting.
    tr.update([det(box=(500, 500, 560, 540))], now=10.0)
    assert len(tr._tracks) == 1
