"""Turns raw detections into database rows, with de-duplication.

The recorder is deliberately free of OpenCV/network concerns so it can be
unit-tested with an in-memory SQLite database.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import numpy as np

from .db import Detection, Plate, get_or_create_stream, utcnow
from .detector import PlateDetection
from .storage import ScreenshotStore

logger = logging.getLogger(__name__)


class Recorder:
    """Persists detections, collapsing repeats within a cooldown window."""

    def __init__(
        self,
        session_factory,
        store: ScreenshotStore,
        min_confidence: float = 0.55,
        dedup_cooldown_seconds: int = 30,
        save_plate_crops: bool = True,
    ) -> None:
        self._Session = session_factory
        self._store = store
        self.min_confidence = min_confidence
        self.cooldown = timedelta(seconds=dedup_cooldown_seconds)
        self.save_plate_crops = save_plate_crops

    def record(
        self,
        stream_name: str,
        stream_url: str,
        detection: PlateDetection,
        frame: np.ndarray | None = None,
    ) -> Detection | None:
        """Record one detection. Returns the Detection row, or None if dropped.

        A new row is created the first time a plate is seen on a stream, or
        after the cooldown elapses. Repeats inside the window update the
        existing row's ``last_seen_at`` and ``count`` instead of spamming.
        """
        if detection.confidence < self.min_confidence:
            return None

        with self._Session() as session:
            stream = get_or_create_stream(session, stream_name, stream_url)
            now = utcnow()

            plate = (
                session.query(Plate)
                .filter_by(plate_number=detection.text)
                .one_or_none()
            )
            if plate is None:
                plate = Plate(
                    plate_number=detection.text,
                    first_seen=now,
                    last_seen=now,
                    sightings=0,
                )
                session.add(plate)
                session.flush()

            # Look for a recent detection of this plate on this stream.
            recent = (
                session.query(Detection)
                .filter(
                    Detection.plate_id == plate.id,
                    Detection.stream_id == stream.id,
                )
                .order_by(Detection.seen_at.desc())
                .first()
            )

            plate.last_seen = now
            plate.sightings += 1

            if recent is not None and (now - recent.last_seen_at) <= self.cooldown:
                recent.last_seen_at = now
                recent.count += 1
                if detection.confidence > recent.confidence:
                    recent.confidence = detection.confidence
                session.commit()
                return recent

            frame_path = crop_path = None
            if frame is not None:
                frame_path, crop_path = self._store.save(
                    frame,
                    stream_id=stream.id,
                    plate_number=detection.text,
                    box=detection.box,
                    save_crop=self.save_plate_crops,
                )

            row = Detection(
                plate_id=plate.id,
                stream_id=stream.id,
                plate_number=detection.text,
                confidence=detection.confidence,
                seen_at=now,
                last_seen_at=now,
                count=1,
                frame_path=frame_path,
                plate_crop_path=crop_path,
            )
            session.add(row)
            session.commit()
            logger.info(
                "Logged plate %s on '%s' (conf=%.2f)",
                detection.text, stream_name, detection.confidence,
            )
            return row
