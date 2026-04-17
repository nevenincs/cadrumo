"""Unit tests for the engine factory."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from aeat.config import Settings
from aeat.storage import StorageError, create_engine_from_settings, dispose_engine

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _settings_for(url: str) -> Settings:
    return Settings(aeat_database_url=url)


def test_engine_round_trips_query_against_tmp_sqlite(tmp_path: Path) -> None:
    """A fresh engine built from settings can execute SQL against a tmp file."""
    db_file = tmp_path / "engine.db"
    settings = _settings_for(f"sqlite:///{db_file.as_posix()}")
    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as conn:
            value = conn.execute(text("select 7")).scalar_one()
        assert value == 7
        assert db_file.exists()
    finally:
        engine.dispose()
        dispose_engine(settings)


def test_engine_creates_parent_directory(tmp_path: Path) -> None:
    """The factory creates missing parent directories for SQLite files."""
    db_file = tmp_path / "nested" / "missing" / "engine.db"
    settings = _settings_for(f"sqlite:///{db_file.as_posix()}")
    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        assert db_file.parent.exists()
    finally:
        engine.dispose()
        dispose_engine(settings)


def test_engine_rejects_empty_url() -> None:
    """An empty URL is fail-fast, not a silent fallback."""
    settings = _settings_for("")
    with pytest.raises(StorageError):
        create_engine_from_settings(settings)
