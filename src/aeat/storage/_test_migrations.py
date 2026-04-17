"""Migration round-trip test.

Applies ``upgrade head`` → ``downgrade base`` → ``upgrade head`` against a
fresh temp SQLite file and then verifies the resulting schema is writable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from ..config import Settings
from . import (
    ModeloRecord,
    ModeloRepository,
    create_engine_from_settings,
    round_trip_migrations,
    session_scope,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def test_migrations_round_trip(tmp_path: Path) -> None:
    """head → base → head must leave the schema writable and consistent."""
    settings = Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}")
    engine = create_engine_from_settings(settings)
    try:
        round_trip_migrations(engine)

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"modelos", "portals", "corpus_artifacts"}.issubset(tables)

        with session_scope(engine) as session:
            ModeloRepository(session).upsert(
                ModeloRecord(identifier="MODELO_130", name="Pagos fraccionados"),
            )

        with session_scope(engine) as session:
            records = ModeloRepository(session).list_all()
        assert len(records) == 1
        assert records[0].identifier == "MODELO_130"
    finally:
        engine.dispose()
