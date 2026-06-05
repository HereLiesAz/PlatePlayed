"""Vehicle attributes: type (car/truck/bus/motorcycle) and dominant color.

Two pieces:

* ``classify_color`` — pure OpenCV/NumPy dominant-color naming. No ML, no
  downloads, fully testable.
* ``VehicleDetector`` — finds vehicle boxes + COCO class. ``YoloVehicleDetector``
  uses ultralytics YOLO (lazy import); ``StubVehicleDetector`` returns nothing so
  the rest of the system runs without the heavy dependency.

``VehicleAnalyzer`` ties them together: for a plate's box it finds the enclosing
vehicle, reads that vehicle's type, and names its color.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np

logger = logging.getLogger(__name__)

Box = tuple[int, int, int, int]

# COCO class ids that are vehicles, mapped to friendly names.
_COCO_VEHICLES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


@dataclass
class VehicleBox:
    """A detected vehicle: pixel box, type name, detector confidence."""

    box: Box
    type: str
    confidence: float


@dataclass
class VehicleInfo:
    """Attributes attached to a plate detection."""

    type: str | None = None
    color: str | None = None
    confidence: float | None = None


# --------------------------------------------------------------------------- #
# Color
# --------------------------------------------------------------------------- #
def classify_color(bgr: np.ndarray | None) -> str:
    """Name the dominant color of a BGR crop. Returns ``"unknown"`` if empty."""
    if bgr is None or bgr.size == 0:
        return "unknown"

    # Sample the central region to avoid background bleeding in at the edges.
    h, w = bgr.shape[:2]
    region = bgr[int(h * 0.2): max(int(h * 0.8), 1), int(w * 0.2): max(int(w * 0.8), 1)]
    if region.size == 0:
        region = bgr

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    hue = float(np.median(hsv[..., 0]))
    sat = float(np.median(hsv[..., 1]))
    val = float(np.median(hsv[..., 2]))

    if val < 50:
        return "black"
    if sat < 35:
        return "white" if val > 200 else "gray"
    return _hue_name(hue)


def _hue_name(hue: float) -> str:
    """Map an OpenCV hue (0–179) to a color name."""
    if hue < 10 or hue >= 170:
        return "red"
    if hue < 22:
        return "orange"
    if hue < 33:
        return "yellow"
    if hue < 78:
        return "green"
    if hue < 100:
        return "cyan"
    if hue < 131:
        return "blue"
    if hue < 150:
        return "purple"
    return "pink"


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
class VehicleDetector(Protocol):
    def detect(self, frame: np.ndarray) -> list[VehicleBox]:
        ...


class StubVehicleDetector:
    """No-op detector — used when ultralytics isn't installed."""

    name = "stub"

    def detect(self, frame: np.ndarray) -> list[VehicleBox]:  # noqa: ARG002
        return []


class YoloVehicleDetector:
    """Vehicle detection via an ultralytics YOLO COCO model."""

    name = "yolo"

    def __init__(self, model: str = "yolov8n.pt", min_confidence: float = 0.4) -> None:
        from ultralytics import YOLO  # lazy, heavy import

        logger.info("Loading YOLO vehicle model: %s", model)
        self._model = YOLO(model)
        self.min_confidence = min_confidence

    def detect(self, frame: np.ndarray) -> list[VehicleBox]:
        result = self._model.predict(frame, verbose=False)[0]
        boxes: list[VehicleBox] = []
        for b in result.boxes:
            name = _COCO_VEHICLES.get(int(b.cls))
            conf = float(b.conf)
            if name is None or conf < self.min_confidence:
                continue
            x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
            boxes.append(VehicleBox((x1, y1, x2, y2), name, conf))
        return boxes


def build_vehicle_detector(
    name: str = "auto", model: str = "yolov8n.pt", min_confidence: float = 0.4
) -> VehicleDetector:
    """Construct a vehicle detector; ``auto`` falls back to the stub."""
    name = (name or "auto").lower()
    if name == "stub":
        return StubVehicleDetector()
    if name in ("auto", "yolo"):
        try:
            return YoloVehicleDetector(model=model, min_confidence=min_confidence)
        except Exception as exc:
            if name == "auto":
                logger.warning(
                    "YOLO vehicle detector unavailable (%s); vehicle type/color "
                    "disabled. Install with: pip install -r requirements-ml.txt",
                    exc,
                )
                return StubVehicleDetector()
            raise
    raise ValueError(f"Unknown vehicle detector: {name!r}")


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
class VehicleAnalyzer:
    """Links a plate to its vehicle and reports the vehicle's type + color."""

    def __init__(self, detector: VehicleDetector, containment_threshold: float = 0.3) -> None:
        self._detector = detector
        self.containment_threshold = containment_threshold

    def detect_vehicles(self, frame: np.ndarray) -> list[VehicleBox]:
        return self._detector.detect(frame)

    def associate(
        self, plate_box: Box, vehicles: list[VehicleBox], frame: np.ndarray
    ) -> VehicleInfo | None:
        """Find the vehicle enclosing ``plate_box`` and read its type/color."""
        best, best_score = None, 0.0
        for vehicle in vehicles:
            score = _containment(plate_box, vehicle.box)
            if score > best_score:
                best, best_score = vehicle, score

        if best is None or best_score < self.containment_threshold:
            return None

        color = classify_color(_crop(frame, best.box))
        return VehicleInfo(type=best.type, color=color, confidence=best.confidence)


def _containment(inner: Box, outer: Box) -> float:
    """Fraction of ``inner``'s area that lies inside ``outer``."""
    ix1, iy1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    ix2, iy2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area = max(0, inner[2] - inner[0]) * max(0, inner[3] - inner[1])
    return inter / area if area > 0 else 0.0


def _crop(frame: np.ndarray, box: Box) -> np.ndarray | None:
    h, w = frame.shape[:2]
    x1 = max(0, min(box[0], box[2]))
    y1 = max(0, min(box[1], box[3]))
    x2 = min(w, max(box[0], box[2]))
    y2 = min(h, max(box[1], box[3]))
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2]
