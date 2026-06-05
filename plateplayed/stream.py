"""Resolve YouTube live streams to playable URLs and yield sampled frames."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def resolve_stream_url(youtube_url: str) -> str:
    """Resolve a YouTube URL to a direct (HLS/HTTP) media URL via yt-dlp."""
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        # Prefer an HLS variant OpenCV can open; fall back to best.
        "format": "best[protocol^=m3u8]/best",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        if "url" in info:
            return info["url"]
        # Some live formats nest the URL inside `formats`.
        formats = info.get("formats") or []
        for fmt in reversed(formats):
            if fmt.get("url"):
                return fmt["url"]
    raise RuntimeError(f"Could not resolve a media URL for {youtube_url}")


def iter_frames(
    youtube_url: str,
    sample_interval_seconds: float = 2.0,
    stop_flag=None,
    reconnect_delay: float = 5.0,
) -> Iterator[np.ndarray]:
    """Yield frames from a YouTube stream, roughly every ``sample_interval``.

    Reconnects automatically on read failure (live streams rotate URLs).
    ``stop_flag`` is any object with truthiness checked via ``stop_flag()``
    or ``stop_flag.is_set()``; iteration ends when it signals stop.
    """
    while not _should_stop(stop_flag):
        try:
            media_url = resolve_stream_url(youtube_url)
        except Exception as exc:
            logger.error("Resolve failed for %s: %s", youtube_url, exc)
            time.sleep(reconnect_delay)
            continue

        cap = cv2.VideoCapture(media_url)
        if not cap.isOpened():
            logger.error("OpenCV could not open stream: %s", youtube_url)
            cap.release()
            time.sleep(reconnect_delay)
            continue

        logger.info("Connected to stream: %s", youtube_url)
        last_emit = 0.0
        try:
            while not _should_stop(stop_flag):
                ok = cap.grab()
                if not ok:
                    logger.warning("Lost frame on %s; reconnecting…", youtube_url)
                    break
                now = time.monotonic()
                if now - last_emit < sample_interval_seconds:
                    continue
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    continue
                last_emit = now
                yield frame
        finally:
            cap.release()

        if not _should_stop(stop_flag):
            time.sleep(reconnect_delay)


def _should_stop(stop_flag) -> bool:
    if stop_flag is None:
        return False
    if hasattr(stop_flag, "is_set"):
        return stop_flag.is_set()
    if callable(stop_flag):
        return bool(stop_flag())
    return bool(stop_flag)
