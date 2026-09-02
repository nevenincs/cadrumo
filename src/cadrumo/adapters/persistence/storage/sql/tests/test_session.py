"""Unit tests for the :func:`cadrumo.adapters.persistence.storage.sql.session.session_scope` unit-of-work helper.

Validates commit-on-success and rollback-on-exception semantics by
running statements through real SQLAlchemy sessions backed by SQLite.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ...errors import StorageValidationError
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from .. import session_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]
_SESSION_LOGGER_NAME = "cadrumo.adapters.persistence.storage.sql.session"


@contextmanager
def _engine(tmp_path: Path) -> Generator[Engine]:
    engine = bootstrap_sqlite_engine(tmp_path / "session.db")
    try:
        yield engine
    finally:
        engine.dispose()


def test_session_scope_commits_on_success(tmp_path: Path) -> None:
    """A normal exit from :func:`session_scope` persists the unit of work."""
    with _engine(tmp_path) as engine:
        with session_scope(engine) as session:
            session.execute(
                text("insert into modelos (identifier, name) values (:identifier, :name)"),
                {"identifier": "MODELO_130", "name": "Pagos fraccionados"},
            )
        with engine.connect() as conn:
            count = conn.execute(text("select count(*) from modelos")).scalar_one()
        assert count == 1


def test_session_scope_rolls_back_and_logs_on_exception(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An exception inside :func:`session_scope` rolls back and logs diagnostics."""
    with _engine(tmp_path) as engine:
        caplog.set_level(logging.DEBUG, logger=_SESSION_LOGGER_NAME)
        with pytest.raises(StorageValidationError), session_scope(engine) as session:
            session.execute(
                text("insert into modelos (identifier, name) values (:identifier, :name)"),
                {"identifier": "MODELO_303", "name": "IVA"},
            )
            raise StorageValidationError(
                translated_message="errors.integrity.integrity_storage_validation",
            )
        with engine.connect() as conn:
            count = conn.execute(text("select count(*) from modelos")).scalar_one()
        assert count == 0
        messages = tuple(record.getMessage() for record in caplog.records if record.name == _SESSION_LOGGER_NAME)
        assert "session_scope rolling back due to exception" in messages
