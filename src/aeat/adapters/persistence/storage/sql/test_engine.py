"""Unit tests for the SQLAlchemy engine factory.

Exercises :func:`aeat.adapters.persistence.storage.sql.create_engine_from_settings`
covering the round-trip happy path, parent-directory creation, fail-fast
on empty URLs, and the project-root anchoring of relative SQLite URLs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from .....core.config import PROJECT_ROOT, Settings
from ..errors import StorageError
from . import create_engine_from_settings, dispose_engine

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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


def test_engine_rejects_empty_url(tmp_path: Path) -> None:
    """An empty URL is fail-fast, not a silent fallback.

    The active-profile resolver leaves ``aeat_database_url`` empty only
    when no profile is selected and no pointer file exists; the test
    anchors ``aeat_local_storage_root`` at an empty tmp directory so the
    resolver cannot pick up a real worktree profile.
    """
    settings = Settings(
        aeat_database_url="",
        aeat_active_profile=None,
        aeat_local_storage_root=tmp_path / "empty-storage-root",
    )
    assert settings.aeat_database_url == ""
    with pytest.raises(StorageError):
        create_engine_from_settings(settings)


def test_engine_anchors_relative_sqlite_urls_to_project_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative SQLite URLs must resolve against PROJECT_ROOT, not the process cwd."""
    relative_db = Path("var") / "pytest-relative-sqlite" / "engine.db"
    anchored_db = PROJECT_ROOT / relative_db
    settings = _settings_for(f"sqlite:///{relative_db.as_posix()}")
    monkeypatch.chdir(tmp_path)
    engine = create_engine_from_settings(settings)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        assert Path(engine.url.database or "") == anchored_db
        assert anchored_db.exists()
        assert not (tmp_path / relative_db).exists()
    finally:
        engine.dispose()
        dispose_engine(settings)
        if anchored_db.exists():
            anchored_db.unlink()
        parent = anchored_db.parent
        while parent != PROJECT_ROOT and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
