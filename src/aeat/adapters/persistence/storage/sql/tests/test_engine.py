"""Unit tests for the SQLAlchemy engine factory.

Exercises :func:`aeat.adapters.persistence.storage.sql.create_engine_from_settings`
covering the round-trip happy path, parent-directory creation, the
storage-root fallback derivation, and the project-root anchoring of
relative SQLite URLs.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from ......core.config import PROJECT_ROOT, Settings
from ...errors import StorageError
from .. import create_engine_from_settings, dispose_engine

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_ENGINE_LOGGER_NAME = "aeat.adapters.persistence.storage.sql.engine"


def _settings_for(url: str) -> Settings:
    return Settings(aeat_database_url=url)


@contextmanager
def _engine_for(settings: Settings) -> Iterator[Any]:
    engine = create_engine_from_settings(settings)
    try:
        yield engine
    finally:
        engine.dispose()
        dispose_engine(settings)


def test_engine_round_trips_query_against_tmp_sqlite(tmp_path: Path) -> None:
    """A fresh engine built from settings can execute SQL against a tmp file."""
    db_file = tmp_path / "engine.db"
    settings = _settings_for(f"sqlite:///{db_file.as_posix()}")
    with _engine_for(settings) as engine:
        with engine.connect() as conn:
            value = conn.execute(text("select 7")).scalar_one()
        assert value == 7
        assert db_file.exists()


def test_engine_applies_concurrency_pragmas(tmp_path: Path) -> None:
    """A file-backed SQLite engine sets busy_timeout (and keeps foreign_keys on)."""
    db_file = tmp_path / "pragmas.db"
    settings = _settings_for(f"sqlite:///{db_file.as_posix()}")
    with _engine_for(settings) as engine, engine.connect() as conn:
        assert conn.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
        assert conn.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_concurrent_writers_do_not_raise_database_locked(tmp_path: Path) -> None:
    """Four threads writing one bucket DB serialise without a database-locked error.

    Under the prior rollback-journal default with ``busy_timeout=0`` a second
    writer fails immediately with ``SQLITE_BUSY`` ("database is locked"); WAL plus
    the busy_timeout makes the loser wait its turn instead. Each thread builds its
    own engine from the same settings so every SQLite connection is created and
    used in the thread that owns it.
    """
    db_file = tmp_path / "concurrent.db"
    settings = _settings_for(f"sqlite:///{db_file.as_posix()}")
    setup_engine = create_engine_from_settings(settings)
    with setup_engine.begin() as conn:
        conn.execute(text("CREATE TABLE writer_probe (id INTEGER PRIMARY KEY AUTOINCREMENT, who TEXT)"))
    setup_engine.dispose()

    worker_count = 4
    writes_per_worker = 25
    errors: list[Exception] = []
    barrier = threading.Barrier(worker_count)

    def worker(name: str) -> None:
        engine = create_engine_from_settings(settings)
        try:
            barrier.wait()
            for _ in range(writes_per_worker):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO writer_probe (who) VALUES (:w)"), {"w": name})
        except Exception as exc:
            errors.append(exc)
        finally:
            engine.dispose()

    threads = [threading.Thread(target=worker, args=(f"w{i}",)) for i in range(worker_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    verify_engine = create_engine_from_settings(settings)
    try:
        assert errors == [], f"concurrent writers raised: {errors!r}"
        with verify_engine.connect() as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM writer_probe")).scalar_one()
        assert total == worker_count * writes_per_worker
    finally:
        verify_engine.dispose()
        dispose_engine(settings)


def test_engine_creates_parent_directory(tmp_path: Path) -> None:
    """The factory creates missing parent directories for SQLite files."""
    db_file = tmp_path / "nested" / "missing" / "engine.db"
    settings = _settings_for(f"sqlite:///{db_file.as_posix()}")
    with _engine_for(settings) as engine:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
        assert db_file.parent.exists()


def test_engine_success_log_does_not_expose_database_path(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_dir = tmp_path / "private-client-storage-root"
    db_file = private_dir / "engine.db"
    settings = _settings_for(f"sqlite:///{db_file.as_posix()}")

    caplog.set_level(logging.DEBUG, logger=_ENGINE_LOGGER_NAME)
    with _engine_for(settings) as engine, engine.connect() as conn:
        conn.execute(text("select 1"))

    messages = tuple(record.getMessage() for record in caplog.records if record.name == _ENGINE_LOGGER_NAME)
    assert any("created engine route_marker=" in message for message in messages)
    assert all("private-client-storage-root" not in message for message in messages)
    assert all("engine.db" not in message for message in messages)


def test_engine_create_failure_does_not_expose_database_path(tmp_path: Path) -> None:
    private_dir = tmp_path / "private-client-storage-root"
    settings = _settings_for(f"unknown+dialect:///{private_dir.as_posix()}/engine.db")

    with pytest.raises(StorageError) as excinfo:
        create_engine_from_settings(settings)

    rendered = str(excinfo.value)
    assert excinfo.value.translated_message == "errors.storage.engine.create_failed"
    assert excinfo.value.context is not None
    assert excinfo.value.context["error_type"] == "NoSuchModuleError"
    assert "route_marker" in excinfo.value.context
    assert "private-client-storage-root" not in rendered
    assert "engine.db" not in rendered


def test_engine_builds_against_derived_storage_root_fallback(tmp_path: Path) -> None:
    """An absent database URL derives a root-level SQLite fallback.

    With no explicit ``aeat_database_url`` and no selected profile, the
    settings layer derives ``sqlite:///<storage-root>/aeat.db`` rather
    than leaving the URL empty; the engine factory then builds a working
    engine against that fallback file. This is the engine-boundary
    counterpart of the config layer's database-URL derivation, and
    guards the operator cold-start path where only
    ``aeat_local_storage_root`` is set.
    """
    storage_root = tmp_path / "derived-storage-root"
    settings = Settings(
        aeat_active_profile=None,
        aeat_local_storage_root=storage_root,
    )
    fallback_db = storage_root / "aeat.db"
    assert settings.aeat_database_url == f"sqlite:///{fallback_db.as_posix()}"
    with _engine_for(settings) as engine:
        with engine.connect() as conn:
            assert conn.execute(text("select 5")).scalar_one() == 5
        assert fallback_db.exists()


def test_engine_anchors_relative_sqlite_urls_to_project_root(tmp_path: Path) -> None:
    """Relative SQLite URLs must resolve against PROJECT_ROOT, not the process cwd."""
    relative_db = Path("var") / "pytest-relative-sqlite" / "engine.db"
    anchored_db = PROJECT_ROOT / relative_db
    settings = _settings_for(f"sqlite:///{relative_db.as_posix()}")
    original_cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        with _engine_for(settings) as engine:
            with engine.connect() as conn:
                conn.execute(text("select 1"))
            assert Path(engine.url.database or "") == anchored_db
            assert anchored_db.exists()
            assert not (tmp_path / relative_db).exists()
    finally:
        os.chdir(original_cwd)
        if anchored_db.exists():
            anchored_db.unlink()
        parent = anchored_db.parent
        while parent != PROJECT_ROOT and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
