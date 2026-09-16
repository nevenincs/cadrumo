"""Regression tests for the SQL substrate's database-level integrity guards.

``secure_objects`` rejects impossible schema versions and malformed
revision/hash metadata at the database layer rather than at the pydantic
record layer.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from ..session import session_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@contextmanager
def _schema_engine(tmp_path: Path, name: str = "constraints.db") -> Generator[Engine]:
    engine = bootstrap_sqlite_engine(tmp_path / name)
    try:
        yield engine
    finally:
        engine.dispose()


def test_secure_object_schema_version_check_constraint(tmp_path: Path) -> None:
    """A raw secure-object insert with schema_version < 1 is rejected."""
    with (
        _schema_engine(tmp_path, "secure-object-schema-version.db") as engine,
        pytest.raises(IntegrityError, match=r"CHECK constraint failed: ck_secure_objects_schema_version_positive"),
        session_scope(engine) as session,
    ):
        session.execute(
            text(
                "insert into secure_objects "
                "(namespace, object_key, classification, schema_version, written_at, payload) "
                "values ('cadrumo-test.raw', :object_key, 'financial', 0, :written_at, :payload)",
            ),
            {
                "object_key": b"raw-key",
                "written_at": datetime(2026, 6, 4, tzinfo=UTC),
                "payload": b"ciphertext",
            },
        )


def test_secure_object_revision_hash_check_constraints(tmp_path: Path) -> None:
    """Raw secure-object revision/hash metadata must use 64-character digests."""
    with (
        _schema_engine(tmp_path, "secure-object-revision-hash.db") as engine,
        pytest.raises(IntegrityError, match=r"CHECK constraint failed: ck_secure_objects_revision_id_len"),
        session_scope(engine) as session,
    ):
        session.execute(
            text(
                "insert into secure_objects "
                "(namespace, object_key, classification, schema_version, written_at, revision_id, payload) "
                "values ('cadrumo-test.raw', :object_key, 'financial', 1, :written_at, 'short', :payload)",
            ),
            {
                "object_key": b"raw-key",
                "written_at": datetime(2026, 6, 4, tzinfo=UTC),
                "payload": b"ciphertext",
            },
        )
