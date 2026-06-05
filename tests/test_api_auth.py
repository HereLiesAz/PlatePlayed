"""Tests for HTTP Basic auth on the dashboard / API."""

import base64
import importlib
import os

from fastapi.testclient import TestClient


def _reload_api(tmp_path, **env):
    """Reload the API module with a clean environment + given overrides."""
    os.environ["PLATEPLAYED_DB_URL"] = f"sqlite:///{tmp_path / 'auth.db'}"
    os.environ["PLATEPLAYED_CONFIG"] = str(tmp_path / "missing.yaml")
    for key in ("PLATEPLAYED_AUTH_USERNAME", "PLATEPLAYED_AUTH_PASSWORD"):
        os.environ.pop(key, None)
    os.environ.update(env)
    import plateplayed.api as api
    return importlib.reload(api)


def _basic(user, password):
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_no_auth_when_password_unset(tmp_path):
    api = _reload_api(tmp_path)
    try:
        client = TestClient(api.app)
        assert client.get("/api/stats").status_code == 200
    finally:
        _reload_api(tmp_path)  # restore unauthenticated module for other tests


def test_auth_required_and_accepts_valid_credentials(tmp_path):
    api = _reload_api(
        tmp_path,
        PLATEPLAYED_AUTH_USERNAME="watcher",
        PLATEPLAYED_AUTH_PASSWORD="s3cret",
    )
    try:
        client = TestClient(api.app)
        assert client.get("/api/stats").status_code == 401
        assert client.get("/api/stats", headers=_basic("watcher", "nope")).status_code == 401
        ok = client.get("/api/stats", headers=_basic("watcher", "s3cret"))
        assert ok.status_code == 200
    finally:
        _reload_api(tmp_path)  # restore unauthenticated module for other tests
