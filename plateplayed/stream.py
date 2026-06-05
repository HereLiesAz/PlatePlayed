"""Resolve YouTube live streams to playable URLs and yield sampled frames."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StreamProbe:
    """Result of checking whether a stream is reachable and decodable."""

    ok: bool
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    frames_read: int = 0
    error: str | None = None


def probe_stream(youtube_url: str, timeout: float = 30.0, frames: int = 5) -> StreamProbe:
    """Resolve, open, and read a few frames to validate a stream.

    Returns a :class:`StreamProbe` with the decoded resolution and nominal FPS,
    or ``ok=False`` and an ``error`` describing where it failed (resolve, open,
    or decode). Never raises.
    """
    try:
        media_url = resolve_stream_url(youtube_url)
    except Exception as exc:
        msg = " ".join(str(exc).split())  # collapse multi-line/whitespace noise
        if len(msg) > 160:
            msg = msg[:157] + "..."
        return StreamProbe(False, error=f"resolve failed: {msg}")

    cap = cv2.VideoCapture(media_url)
    if not cap.isOpened():
        cap.release()
        return StreamProbe(False, error="OpenCV could not open the stream")

    try:
        reported_fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None

        read = 0
        last_frame = None
        deadline = time.monotonic() + timeout
        while read < frames and time.monotonic() < deadline:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            last_frame = frame
            read += 1

        if read == 0:
            return StreamProbe(False, width, height, error="opened but decoded no frames")

        if last_frame is not None:
            height, width = last_frame.shape[:2]
        fps = reported_fps if reported_fps and reported_fps > 0 else None
        return StreamProbe(True, width, height, fps, read)
    finally:
        cap.release()


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
