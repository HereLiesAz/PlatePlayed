"""Tests for configuration loading and overrides."""

from plateplayed.config import load_config


def test_defaults_when_file_missing(tmp_path):
    cfg = load_config(tmp_path / "nope.yaml")
    assert cfg.database_url.startswith("sqlite:///")
    assert cfg.streams == []
    assert cfg.detector == "auto"


def test_loads_streams_and_filters_enabled(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        """
database_url: "sqlite:///x.db"
min_confidence: 0.7
streams:
  - name: A
    url: http://a
    enabled: true
  - name: B
    url: http://b
    enabled: false
"""
    )
    cfg = load_config(p)
    assert cfg.min_confidence == 0.7
    assert len(cfg.streams) == 2
    assert [s.name for s in cfg.enabled_streams] == ["A"]


def test_env_overrides_db_url(tmp_path, monkeypatch):
    monkeypatch.setenv("PLATEPLAYED_DB_URL", "sqlite:///override.db")
    cfg = load_config(tmp_path / "nope.yaml")
    assert cfg.database_url == "sqlite:///override.db"
