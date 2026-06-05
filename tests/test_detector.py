"""Tests for detector selection and plate normalization."""

import numpy as np

from plateplayed.detector import StubDetector, _normalize_plate, build_detector


def test_stub_returns_empty():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    assert StubDetector().detect(frame) == []


def test_build_stub_explicitly():
    d = build_detector("stub")
    assert isinstance(d, StubDetector)


def test_build_auto_falls_back_to_stub_without_ml():
    # fast-alpr is not installed in the test environment, so auto -> stub.
    d = build_detector("auto")
    assert d.detect(np.zeros((10, 10, 3), dtype=np.uint8)) == []


def test_normalize_plate():
    assert _normalize_plate("ab 12-cd") == "AB12CD"
    assert _normalize_plate("  7gh!9  ") == "7GH9"
    assert _normalize_plate("") == ""
