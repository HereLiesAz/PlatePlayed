"""Multi-frame plate tracking with best-read voting.

A physical vehicle appears in several consecutive sampled frames. Running OCR
on each frame independently produces duplicate — and often slightly different —
reads (``ABC123`` vs ``ABCl23``). ``PlateTracker`` groups detections of the
same plate across frames into a *track*, then emits a single **consensus** read
(the most-voted text, with the highest-confidence crop) and only after a track
has been seen enough times to suppress one-frame false positives.

The tracker is per-stream and intentionally free of OpenCV/DB concerns so it can
be unit-tested with synthetic ``PlateDetection`` lists.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from itertools import count

from .detector import PlateDetection

logger = logging.getLogger(__name__)

Box = tuple[int, int, int, int]


def iou(a: Box, b: Box) -> float:
    """Intersection-over-union of two ``(x1, y1, x2, y2)`` boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    """One physical plate followed across frames."""

    id: int
    box: Box
    first_seen: float
    last_seen: float
    hits: int = 0
    votes: Counter = field(default_factory=Counter)
    # text -> best (confidence, box) seen for that text
    best_by_text: dict[str, tuple[float, Box]] = field(default_factory=dict)

    def add(self, det: PlateDetection, now: float) -> None:
        self.hits += 1
        self.last_seen = now
        self.box = det.box
        self.votes[det.text] += 1
        prev = self.best_by_text.get(det.text)
        if prev is None or det.confidence > prev[0]:
            self.best_by_text[det.text] = (det.confidence, det.box)

    def consensus(self) -> PlateDetection:
        """Best read for this track: most votes, tie-broken by confidence."""
        winner = max(self.votes, key=lambda t: (self.votes[t], self.best_by_text[t][0]))
        confidence, box = self.best_by_text[winner]
        return PlateDetection(text=winner, confidence=confidence, box=box)


class PlateTracker:
    """Groups per-frame detections into tracks and emits consensus reads."""

    def __init__(
        self,
        iou_threshold: float = 0.3,
        min_hits: int = 2,
        max_age_seconds: float = 5.0,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.min_hits = min_hits
        self.max_age = max_age_seconds
        self._tracks: list[Track] = []
        self._ids = count(1)

    def update(self, detections: list[PlateDetection], now: float) -> list[PlateDetection]:
        """Fold a frame's detections into tracks; return consensus reads.

        Returns one consensus ``PlateDetection`` per track that was updated this
        frame *and* has reached ``min_hits``. Downstream de-duplication (the
        recorder's cooldown) collapses repeated emissions of a long-lived track
        into a single database row.
        """
        # Drop tracks we haven't seen recently.
        self._tracks = [t for t in self._tracks if now - t.last_seen <= self.max_age]

        updated_ids: set[int] = set()
        for det in detections:
            track = self._match(det)
            if track is None:
                track = Track(id=next(self._ids), box=det.box, first_seen=now, last_seen=now)
                self._tracks.append(track)
            track.add(det, now)
            updated_ids.add(track.id)

        return [
            t.consensus()
            for t in self._tracks
            if t.id in updated_ids and t.hits >= self.min_hits
        ]

    def _match(self, det: PlateDetection) -> Track | None:
        """Match a detection to an existing track by overlap, else exact text."""
        best, best_iou = None, 0.0
        for t in self._tracks:
            score = iou(det.box, t.box)
            if score > best_iou:
                best, best_iou = t, score
        if best is not None and best_iou >= self.iou_threshold:
            return best
        # Spatial match failed (e.g. a fast car jumped position) — fall back to
        # an exact text match against an active track.
        if det.text:
            for t in self._tracks:
                if det.text in t.votes:
                    return t
        return None
