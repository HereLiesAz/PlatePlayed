"""Tests for vehicle color naming, detector selection, and association."""

import numpy as np

from plateplayed.vehicle import (
    StubVehicleDetector,
    VehicleAnalyzer,
    VehicleBox,
    build_vehicle_detector,
    classify_color,
)


def solid(bgr, h=40, w=60):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:] = bgr
    return img


def test_classify_primary_colors():
    assert classify_color(solid((0, 0, 255))) == "red"
    assert classify_color(solid((255, 0, 0))) == "blue"
    assert classify_color(solid((0, 255, 0))) == "green"
    assert classify_color(solid((0, 255, 255))) == "yellow"


def test_classify_neutrals():
    assert classify_color(solid((0, 0, 0))) == "black"
    assert classify_color(solid((255, 255, 255))) == "white"
    assert classify_color(solid((128, 128, 128))) == "gray"


def test_classify_empty_is_unknown():
    assert classify_color(None) == "unknown"
    assert classify_color(np.zeros((0, 0, 3), dtype=np.uint8)) == "unknown"


def test_build_auto_falls_back_to_stub_without_ml():
    d = build_vehicle_detector("auto")
    assert d.detect(np.zeros((10, 10, 3), dtype=np.uint8)) == []


def test_associate_picks_enclosing_vehicle():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    frame[:] = (0, 0, 255)  # red everywhere → color should read red
    vehicles = [
        VehicleBox((0, 0, 100, 100), "truck", 0.9),
        VehicleBox((100, 100, 200, 200), "car", 0.8),
    ]
    analyzer = VehicleAnalyzer(StubVehicleDetector())
    # Plate sits inside the second (car) box.
    info = analyzer.associate((150, 150, 170, 160), vehicles, frame)
    assert info is not None
    assert info.type == "car"
    assert info.color == "red"
    assert info.confidence == 0.8


def test_associate_returns_none_without_overlap():
    frame = np.zeros((200, 200, 3), dtype=np.uint8)
    vehicles = [VehicleBox((0, 0, 50, 50), "car", 0.9)]
    analyzer = VehicleAnalyzer(StubVehicleDetector())
    assert analyzer.associate((150, 150, 170, 160), vehicles, frame) is None


def test_associate_empty_vehicles_is_none():
    frame = np.zeros((50, 50, 3), dtype=np.uint8)
    analyzer = VehicleAnalyzer(StubVehicleDetector())
    assert analyzer.associate((10, 10, 20, 20), [], frame) is None
