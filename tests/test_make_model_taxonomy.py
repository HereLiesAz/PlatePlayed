"""Phase 0 tests: make/model and taxonomy interfaces, stubs, and wiring."""

import numpy as np
import pytest

from plateplayed.make_model import (
    MakeModelResult,
    StubMakeModelClassifier,
    build_make_model_classifier,
)
from plateplayed.taxonomy import (
    StubTaxonomyClassifier,
    TaxonomyResult,
    build_taxonomy_classifier,
)
from plateplayed.vehicle import StubVehicleDetector, VehicleAnalyzer, VehicleBox

CROP = np.zeros((10, 10, 3), dtype=np.uint8)


def test_make_model_stub_and_auto_return_none():
    assert StubMakeModelClassifier().classify(CROP) is None
    assert build_make_model_classifier("auto").classify(CROP) is None


def test_taxonomy_stub_and_auto_return_none():
    assert StubTaxonomyClassifier().classify(CROP) is None
    assert build_taxonomy_classifier("auto").classify(CROP) is None


def test_unimplemented_backends_raise():
    with pytest.raises(NotImplementedError):
        build_make_model_classifier("onnx")
    with pytest.raises(NotImplementedError):
        build_make_model_classifier("api")
    with pytest.raises(NotImplementedError):
        build_taxonomy_classifier("onnx")


def test_unknown_backend_raises_value_error():
    with pytest.raises(ValueError):
        build_make_model_classifier("nope")
    with pytest.raises(ValueError):
        build_taxonomy_classifier("nope")


class _FakeMakeModel:
    def classify(self, crop):
        return MakeModelResult(make="Toyota", model="Camry", confidence=0.82)


class _FakeTaxonomy:
    def classify(self, crop):
        return TaxonomyResult(category="police", confidence=0.77)


def test_analyzer_fills_make_model_and_category():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[:] = (0, 0, 255)  # red
    vehicles = [VehicleBox((0, 0, 200, 200), "car", 0.9)]
    analyzer = VehicleAnalyzer(
        StubVehicleDetector(),
        make_model_classifier=_FakeMakeModel(),
        taxonomy_classifier=_FakeTaxonomy(),
    )
    info = analyzer.associate((50, 50, 70, 60), vehicles, frame)
    assert info.type == "car"
    assert info.color == "red"
    assert (info.make, info.model) == ("Toyota", "Camry")
    assert info.make_model_confidence == 0.82
    assert info.category == "police"
    assert info.category_confidence == 0.77


def test_analyzer_without_classifiers_leaves_fields_none():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    vehicles = [VehicleBox((0, 0, 200, 200), "truck", 0.9)]
    info = VehicleAnalyzer(StubVehicleDetector()).associate((50, 50, 70, 60), vehicles, frame)
    assert info.make is None and info.model is None and info.category is None
