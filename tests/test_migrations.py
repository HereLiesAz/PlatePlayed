"""Verify the Alembic migration produces the same schema as the models."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect

from plateplayed.db import Base

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_migration_matches_models(tmp_path, monkeypatch):
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("PLATEPLAYED_DB_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("PLATEPLAYED_CONFIG", str(tmp_path / "missing.yaml"))

    command.upgrade(AlembicConfig(str(REPO_ROOT / "alembic.ini")), "head")

    engine = create_engine(f"sqlite:///{db_path}")
    migrated_tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
    model_tables = set(Base.metadata.tables.keys())
    assert migrated_tables == model_tables

    # Columns of the detections table must line up with the model.
    migrated_cols = {c["name"] for c in inspect(engine).get_columns("detections")}
    model_cols = {c.name for c in Base.metadata.tables["detections"].columns}
    assert migrated_cols == model_cols
