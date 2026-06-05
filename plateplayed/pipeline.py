"""Orchestrator: build shared resources and run a worker per stream."""

from __future__ import annotations

import logging
import threading
import time

from .config import Config
from .db import init_db
from .detector import build_detector
from .recorder import Recorder
from .storage import ScreenshotStore
from .worker import StreamWorker

logger = logging.getLogger(__name__)


class Pipeline:
    """Owns the detector, DB, recorder, and the set of stream workers."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.session_factory = init_db(config.database_url)
        self.detector = build_detector(config.detector)
        self.store = ScreenshotStore(config.screenshot_dir)
        self.recorder = Recorder(
            self.session_factory,
            self.store,
            min_confidence=config.min_confidence,
            dedup_cooldown_seconds=config.dedup_cooldown_seconds,
            save_plate_crops=config.save_plate_crops,
        )
        self._detect_lock = threading.Lock()
        self._workers: list[StreamWorker] = []

    def run(self) -> None:
        """Start all enabled stream workers and block until interrupted."""
        streams = self.config.enabled_streams
        if not streams:
            logger.warning("No enabled streams in config. Nothing to do.")
            return

        logger.info(
            "Starting pipeline: %d stream(s), detector=%s",
            len(streams), getattr(self.detector, "name", "unknown"),
        )
        for stream in streams:
            worker = StreamWorker(
                stream,
                self.detector,
                self.recorder,
                sample_interval_seconds=self.config.sample_interval_seconds,
                detect_lock=self._detect_lock,
            )
            worker.start()
            self._workers.append(worker)

        try:
            while any(w.is_alive() for w in self._workers):
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Interrupted — shutting down workers…")
            self.stop()

    def stop(self) -> None:
        for worker in self._workers:
            worker.stop()
        for worker in self._workers:
            worker.join(timeout=10.0)
