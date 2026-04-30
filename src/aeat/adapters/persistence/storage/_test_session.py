"""Unit tests for the session_scope unit-of-work helper."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from ....core.config import Settings
from . import create_engine_from_settings, session_scope
from ._orm import Base

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _engine(tmp_path: Path):
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'session.db').as_posix()}")
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    return engine


def test_session_scope_commits_on_success(tmp_path: Path) -> None:
    """A normal exit from session_scope must persist the unit of work."""
    engine = _engine(tmp_path)
    try:
        with session_scope(engine) as session:
            session.execute(
                text("insert into modelos (identifier, name) values (:identifier, :name)"),
                {"identifier": "MODELO_130", "name": "Pagos fraccionados"},
            )
        with engine.connect() as conn:
            count = conn.execute(text("select count(*) from modelos")).scalar_one()
        assert count == 1
    finally:
        engine.dispose()


def test_session_scope_rolls_back_on_exception(tmp_path: Path) -> None:
    """An exception inside session_scope must roll back the unit of work."""
    engine = _engine(tmp_path)

    class BoomError(RuntimeError):
        pass

    try:
        with pytest.raises(BoomError), session_scope(engine) as session:
            session.execute(
                text("insert into modelos (identifier, name) values (:identifier, :name)"),
                {"identifier": "MODELO_303", "name": "IVA"},
            )
            raise BoomError("rollback me")
        with engine.connect() as conn:
            count = conn.execute(text("select count(*) from modelos")).scalar_one()
        assert count == 0
    finally:
        engine.dispose()
