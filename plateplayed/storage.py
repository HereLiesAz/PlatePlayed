"""Screenshot storage: write full frames and cropped plate images to disk."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ScreenshotStore:
    """Writes detection screenshots under a per-stream, per-day directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir_for(self, stream_id: int) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        target = self.root / f"stream_{stream_id}" / day
        target.mkdir(parents=True, exist_ok=True)
        return target

    def save(
        self,
        frame: np.ndarray,
        stream_id: int,
        plate_number: str,
        box: tuple[int, int, int, int] | None = None,
        save_crop: bool = True,
    ) -> tuple[str | None, str | None]:
        """Save the full frame (and optional plate crop).

        Returns ``(frame_path, crop_path)`` as strings relative to nothing in
        particular — they're stored verbatim and served by the API.
        """
        ts = datetime.now(timezone.utc).strftime("%H%M%S_%f")
        safe_plate = "".join(c for c in plate_number if c.isalnum()) or "unknown"
        directory = self._dir_for(stream_id)

        frame_path = directory / f"{ts}_{safe_plate}_frame.jpg"
        crop_path: Path | None = None
        try:
            cv2.imwrite(str(frame_path), frame)
        except Exception as exc:
            logger.error("Failed to write frame screenshot: %s", exc)
            return None, None

        if save_crop and box is not None:
            crop = _crop(frame, box, pad=8)
            if crop is not None and crop.size > 0:
                crop_path = directory / f"{ts}_{safe_plate}_plate.jpg"
                try:
                    cv2.imwrite(str(crop_path), crop)
                except Exception as exc:
                    logger.error("Failed to write plate crop: %s", exc)
                    crop_path = None

        return str(frame_path), (str(crop_path) if crop_path else None)


def _crop(
    frame: np.ndarray, box: tuple[int, int, int, int], pad: int = 0
) -> np.ndarray | None:
    """Return a padded crop of ``box`` clamped to frame bounds."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(x1, x2) - pad)
    y1 = max(0, min(y1, y2) - pad)
    x2 = min(w, max(x1, x2) + pad)
    y2 = min(h, max(y1, y2) + pad)
    if x2 <= x1 or y2 <= y1:
        return None
    return frame[y1:y2, x1:x2].copy()
