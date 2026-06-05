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
        streams=streams,
    )

    env_db = os.environ.get("PLATEPLAYED_DB_URL")
    if env_db:
        config.database_url = env_db

    return config
