"""License-plate detection + OCR.

A small interface (`Detector`) with two implementations:

* `FastAlprDetector` — real ML via the ``fast-alpr`` package (YOLO plate
  detector + ONNX OCR). CPU-friendly; downloads model weights on first use.
* `StubDetector`     — returns nothing. Lets the full pipeline, database,
  API, and tests run without the heavy ML dependencies.

`build_detector()` picks the right one based on config and what's installed.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PlateDetection:
    """A single detected plate within a frame."""

    text: str
    confidence: float
    # Bounding box in pixels: (x1, y1, x2, y2).
    box: tuple[int, int, int, int]


class Detector(Protocol):
    """Anything that can find plates in a BGR frame."""

    def detect(self, frame: np.ndarray) -> list[PlateDetection]:
        ...


class StubDetector:
    """No-op detector. Always returns an empty list.

    Used when ``fast-alpr`` isn't installed or ``detector: stub`` is set.
    """

    name = "stub"

    def detect(self, frame: np.ndarray) -> list[PlateDetection]:  # noqa: ARG002
        return []


class FastAlprDetector:
    """Real ALPR engine backed by the ``fast-alpr`` package."""

    name = "fast-alpr"

    def __init__(
        self,
        detector_model: str = "yolo-v9-t-384-license-plate-end2end",
        ocr_model: str = "global-plates-mobile-vit-v2-model",
    ) -> None:
        from fast_alpr import ALPR  # imported lazily; heavy dependency

        logger.info("Loading fast-alpr models (detector=%s, ocr=%s)…",
                     detector_model, ocr_model)
        self._alpr = ALPR(detector_model=detector_model, ocr_model=ocr_model)

    def detect(self, frame: np.ndarray) -> list[PlateDetection]:
        results = self._alpr.predict(frame)
        detections: list[PlateDetection] = []
        for r in results:
            ocr = getattr(r, "ocr", None)
            if ocr is None or not getattr(ocr, "text", None):
                continue
            bbox = r.detection.bounding_box
            box = (
                int(bbox.x1),
                int(bbox.y1),
                int(bbox.x2),
                int(bbox.y2),
            )
            text = _normalize_plate(ocr.text)
            if not text:
                continue
            detections.append(
                PlateDetection(
                    text=text,
                    confidence=_ocr_confidence(getattr(ocr, "confidence", 0.0)),
                    box=box,
                )
            )
        return detections


def _ocr_confidence(confidence: float | list[float] | None) -> float:
    """Collapse fast-alpr's OCR confidence to a single 0..1 score.

    The default OCR model returns one probability *per character*
    (``list[float]``); other backends may return a single ``float``. We average
    the per-character values, matching how fast-alpr aggregates them itself.
    """
    if isinstance(confidence, (list, tuple)):
        return statistics.mean(confidence) if confidence else 0.0
    return float(confidence or 0.0)


def _normalize_plate(text: str) -> str:
    """Uppercase and strip non-alphanumeric characters from OCR output."""
    return "".join(ch for ch in text.upper() if ch.isalnum())


def build_detector(name: str = "auto") -> Detector:
    """Construct a detector by name.

    ``"auto"`` uses fast-alpr when importable, else the stub.
    """
    name = (name or "auto").lower()

    if name == "stub":
        logger.info("Using StubDetector (no ML).")
        return StubDetector()

    if name in ("auto", "fast-alpr", "fast_alpr"):
        try:
            return FastAlprDetector()
        except Exception as exc:  # ImportError or model-load failure
            if name == "auto":
                logger.warning(
                    "fast-alpr unavailable (%s); falling back to StubDetector. "
                    "Install ML deps with: pip install -r requirements-ml.txt",
                    exc,
                )
                return StubDetector()
            raise

    raise ValueError(f"Unknown detector: {name!r}")
