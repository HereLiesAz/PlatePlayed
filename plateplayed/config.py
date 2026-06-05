"""Configuration loading for PlatePlayed.

Reads a YAML file into typed dataclasses and applies environment overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class StreamConfig:
    """A single YouTube stream to watch."""

    name: str
    url: str
    enabled: bool = True


@dataclass
class Config:
    """Top-level application configuration."""

    database_url: str = "sqlite:///data/plateplayed.db"
    screenshot_dir: str = "data/screenshots"
    detector: str = "auto"
    min_confidence: float = 0.55
    sample_interval_seconds: float = 2.0
    dedup_cooldown_seconds: int = 30
    save_plate_crops: bool = True

    # Multi-frame tracking + best-read voting.
    tracking_enabled: bool = True
    track_min_hits: int = 2
    track_iou_threshold: float = 0.3
    track_max_age_seconds: float = 5.0

    # Vehicle attributes (type + color). Needs the YOLO model from the ML extras;
    # falls back to "no attributes" when unavailable.
    vehicle_enabled: bool = True
    vehicle_detector: str = "auto"
    vehicle_model: str = "yolov8n.pt"
    vehicle_min_confidence: float = 0.4

    # Make/model recognition (Phase 0 — stub only; needs vehicle detection on).
    make_model_enabled: bool = False
    make_model_backend: str = "auto"
    make_model_path: str | None = None
    make_model_min_confidence: float = 0.5
    make_model_region: str | None = None

    # Rich vehicle taxonomy (Phase 0 — stub only; needs vehicle detection on).
    taxonomy_enabled: bool = False
    taxonomy_backend: str = "auto"
    taxonomy_model_path: str | None = None
    taxonomy_version: str = "v1"
    taxonomy_min_confidence: float = 0.5
    taxonomy_emergency_requires_corroboration: bool = True

    # Watchlist alerting on matching plate sightings.
    alerts_enabled: bool = True
    alert_cooldown_seconds: int = 300
    alert_webhook_url: str | None = None

    # Dashboard / API HTTP Basic auth. Auth is enforced when a password is set.
    auth_username: str = "admin"
    auth_password: str | None = None

    streams: list[StreamConfig] = field(default_factory=list)

    @property
    def enabled_streams(self) -> list[StreamConfig]:
        return [s for s in self.streams if s.enabled]


def load_config(path: str | os.PathLike[str] = "config.yaml") -> Config:
    """Load configuration from ``path``, falling back to defaults.

    If the file is missing, defaults are used (handy for tests). The
    ``PLATEPLAYED_DB_URL`` environment variable overrides ``database_url``.
    """
    data: dict = {}
    config_path = Path(path)
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}

    streams = [
        StreamConfig(
            name=s.get("name", s.get("url", "unnamed")),
            url=s["url"],
            enabled=s.get("enabled", True),
        )
        for s in data.get("streams", [])
    ]

    tracking = data.get("tracking") or {}
    vehicle = data.get("vehicle") or {}
    make_model = data.get("make_model") or {}
    taxonomy = data.get("taxonomy") or {}
    alerts = data.get("alerts") or {}
    auth = data.get("auth") or {}

    config = Config(
        database_url=data.get("database_url", Config.database_url),
        screenshot_dir=data.get("screenshot_dir", Config.screenshot_dir),
        detector=data.get("detector", Config.detector),
        min_confidence=float(data.get("min_confidence", Config.min_confidence)),
        sample_interval_seconds=float(
            data.get("sample_interval_seconds", Config.sample_interval_seconds)
        ),
        dedup_cooldown_seconds=int(
            data.get("dedup_cooldown_seconds", Config.dedup_cooldown_seconds)
        ),
        save_plate_crops=bool(data.get("save_plate_crops", Config.save_plate_crops)),
        tracking_enabled=bool(tracking.get("enabled", Config.tracking_enabled)),
        track_min_hits=int(tracking.get("min_hits", Config.track_min_hits)),
        track_iou_threshold=float(
            tracking.get("iou_threshold", Config.track_iou_threshold)
        ),
        track_max_age_seconds=float(
            tracking.get("max_age_seconds", Config.track_max_age_seconds)
        ),
        vehicle_enabled=bool(vehicle.get("enabled", Config.vehicle_enabled)),
        vehicle_detector=vehicle.get("detector", Config.vehicle_detector),
        vehicle_model=vehicle.get("model", Config.vehicle_model),
        vehicle_min_confidence=float(
            vehicle.get("min_confidence", Config.vehicle_min_confidence)
        ),
        make_model_enabled=bool(make_model.get("enabled", Config.make_model_enabled)),
        make_model_backend=make_model.get("backend", Config.make_model_backend),
        make_model_path=make_model.get("model_path", Config.make_model_path),
        make_model_min_confidence=float(
            make_model.get("min_confidence", Config.make_model_min_confidence)
        ),
        make_model_region=make_model.get("region", Config.make_model_region),
        taxonomy_enabled=bool(taxonomy.get("enabled", Config.taxonomy_enabled)),
        taxonomy_backend=taxonomy.get("backend", Config.taxonomy_backend),
        taxonomy_model_path=taxonomy.get("model_path", Config.taxonomy_model_path),
        taxonomy_version=taxonomy.get("version", Config.taxonomy_version),
        taxonomy_min_confidence=float(
            taxonomy.get("min_confidence", Config.taxonomy_min_confidence)
        ),
        taxonomy_emergency_requires_corroboration=bool(
            taxonomy.get(
                "emergency_requires_corroboration",
                Config.taxonomy_emergency_requires_corroboration,
            )
        ),
        alerts_enabled=bool(alerts.get("enabled", Config.alerts_enabled)),
        alert_cooldown_seconds=int(
            alerts.get("cooldown_seconds", Config.alert_cooldown_seconds)
        ),
        alert_webhook_url=alerts.get("webhook_url", Config.alert_webhook_url),
        auth_username=auth.get("username", Config.auth_username),
        auth_password=auth.get("password", Config.auth_password),
        streams=streams,
    )

    env_db = os.environ.get("PLATEPLAYED_DB_URL")
    if env_db:
        config.database_url = env_db

    # Credentials are most safely supplied via the environment.
    config.auth_username = os.environ.get("PLATEPLAYED_AUTH_USERNAME", config.auth_username)
    config.auth_password = os.environ.get("PLATEPLAYED_AUTH_PASSWORD", config.auth_password)
    config.alert_webhook_url = os.environ.get(
        "PLATEPLAYED_ALERT_WEBHOOK", config.alert_webhook_url
    )

    return config
