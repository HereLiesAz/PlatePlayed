"""Tests for detector selection and plate normalization."""

from types import SimpleNamespace

import numpy as np
import pytest

from plateplayed.detector import (
    FastAlprDetector,
    PlateDetection,
    StubDetector,
    _normalize_plate,
    _ocr_confidence,
    build_detector,
)


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


def test_ocr_confidence_handles_per_character_list():
    # fast-alpr's default OCR returns one probability per character.
    assert _ocr_confidence([0.9, 0.8, 1.0]) == pytest.approx(0.9)


def test_ocr_confidence_handles_scalar_and_empty():
    assert _ocr_confidence(0.75) == pytest.approx(0.75)
    assert _ocr_confidence([]) == 0.0
    assert _ocr_confidence(None) == 0.0


def _fake_alpr_result(text, confidence, box):
    """Mimic fast-alpr's ALPRResult object shape (detection + ocr)."""
    x1, y1, x2, y2 = box
    return SimpleNamespace(
        detection=SimpleNamespace(
            bounding_box=SimpleNamespace(x1=x1, y1=y1, x2=x2, y2=y2)
        ),
        ocr=SimpleNamespace(text=text, confidence=confidence),
    )


def test_fastalpr_detect_parses_results_without_models():
    """Exercise the result-parsing path with a stand-in for the ALPR engine.

    Avoids the heavy fast-alpr dependency / model download while still
    verifying that per-character confidence lists, normalization, and empty
    OCR results are handled the way the real library returns them.
    """
    ocr_none = SimpleNamespace(
        detection=SimpleNamespace(bounding_box=SimpleNamespace(x1=1, y1=2, x2=3, y2=4)),
        ocr=None,
    )
    detector = FastAlprDetector.__new__(FastAlprDetector)  # skip model loading
    detector._alpr = SimpleNamespace(
        predict=lambda frame: [
            _fake_alpr_result("ab-12 cd", [0.9, 0.8, 1.0, 0.9], (10, 20, 110, 60)),
            _fake_alpr_result("", [0.5], (0, 0, 5, 5)),     # empty text -> skipped
            _fake_alpr_result("!!!", [0.5], (0, 0, 5, 5)),  # normalizes to empty -> skipped
            ocr_none,                                        # ocr is None -> skipped
        ]
    )

    out = detector.detect(np.zeros((100, 200, 3), dtype=np.uint8))

    assert out == [
        PlateDetection(text="AB12CD", confidence=pytest.approx(0.9), box=(10, 20, 110, 60))
    ]
