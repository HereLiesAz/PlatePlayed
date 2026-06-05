"""Offline tests for stream probing, using fake resolve + VideoCapture."""

import cv2
import numpy as np

import plateplayed.stream as stream
from plateplayed.stream import probe_stream


class _FakeCap:
    """Minimal cv2.VideoCapture stand-in yielding `n_frames` then EOF."""

    def __init__(self, url, *, opened=True, n_frames=3, w=1920, h=1080, fps=30.0):
        self._n = 0
        self._opened = opened
        self.n_frames = n_frames
        self._w, self._h, self._fps = w, h, fps

    def isOpened(self):
        return self._opened

    def get(self, prop):
        return {
            cv2.CAP_PROP_FPS: self._fps,
            cv2.CAP_PROP_FRAME_WIDTH: self._w,
            cv2.CAP_PROP_FRAME_HEIGHT: self._h,
        }.get(prop, 0)

    def read(self):
        if self._n >= self.n_frames:
            return False, None
        self._n += 1
        return True, np.zeros((self._h, self._w, 3), dtype=np.uint8)

    def release(self):
        pass


def _patch(monkeypatch, *, resolve_exc=None, cap_factory=_FakeCap):
    if resolve_exc is not None:
        def _raise(url):
            raise resolve_exc
        monkeypatch.setattr(stream, "resolve_stream_url", _raise)
    else:
        monkeypatch.setattr(stream, "resolve_stream_url", lambda url: "http://media/x.m3u8")
    monkeypatch.setattr(cv2, "VideoCapture", cap_factory)


def test_probe_ok_reports_resolution_and_fps(monkeypatch):
    _patch(monkeypatch)
    p = probe_stream("https://youtu.be/x", frames=5)
    assert p.ok
    assert (p.width, p.height) == (1920, 1080)
    assert p.fps == 30.0
    assert p.frames_read == 3  # fake yields 3 then EOF


def test_probe_resolve_failure(monkeypatch):
    _patch(monkeypatch, resolve_exc=RuntimeError("no formats"))
    p = probe_stream("https://youtu.be/x")
    assert not p.ok
    assert "resolve failed" in p.error


def test_probe_cannot_open(monkeypatch):
    _patch(monkeypatch, cap_factory=lambda url: _FakeCap(url, opened=False))
    p = probe_stream("https://youtu.be/x")
    assert not p.ok
    assert "could not open" in p.error


def test_probe_opens_but_no_frames(monkeypatch):
    _patch(monkeypatch, cap_factory=lambda url: _FakeCap(url, n_frames=0))
    p = probe_stream("https://youtu.be/x")
    assert not p.ok
    assert "no frames" in p.error
