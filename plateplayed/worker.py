"""Per-stream worker: pull frames, run detection, hand results to the recorder."""

from __future__ import annotations

import logging
import threading
import time

from .config import StreamConfig
from .detector import Detector
from .recorder import Recorder
from .stream import iter_frames
from .tracking import PlateTracker

logger = logging.getLogger(__name__)


class StreamWorker(threading.Thread):
    """Runs one stream's detection loop on its own thread."""

    def __init__(
        self,
        stream: StreamConfig,
        detector: Detector,
        recorder: Recorder,
        sample_interval_seconds: float = 2.0,
        detect_lock: threading.Lock | None = None,
        tracker: PlateTracker | None = None,
    ) -> None:
        super().__init__(name=f"worker-{stream.name}", daemon=True)
        self.stream = stream
        self.detector = detector
        self.recorder = recorder
        self.sample_interval = sample_interval_seconds
        # Serialize detector access — most ALPR backends aren't thread-safe.
        self._detect_lock = detect_lock or threading.Lock()
        # Per-stream tracker (None disables multi-frame voting).
        self._tracker = tracker
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        logger.info("Worker starting for '%s'", self.stream.name)
        try:
            for frame in iter_frames(
                self.stream.url,
                sample_interval_seconds=self.sample_interval,
                stop_flag=self._stop,
            ):
                try:
                    with self._detect_lock:
                        detections = self.detector.detect(frame)
                except Exception as exc:
                    logger.error("Detection error on '%s': %s", self.stream.name, exc)
                    continue

                # Collapse multi-frame detections into voted consensus reads.
                if self._tracker is not None:
                    detections = self._tracker.update(detections, time.monotonic())

                for det in detections:
                    try:
                        self.recorder.record(
                            stream_name=self.stream.name,
                            stream_url=self.stream.url,
                            detection=det,
                            frame=frame,
                        )
                    except Exception as exc:
                        logger.error("Record error on '%s': %s", self.stream.name, exc)
        except Exception as exc:  # pragma: no cover - top-level safety net
            logger.exception("Worker for '%s' crashed: %s", self.stream.name, exc)
        finally:
            logger.info("Worker stopped for '%s'", self.stream.name)
