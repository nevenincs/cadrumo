"""Runtime contracts for secure-object hash columns."""

from __future__ import annotations

import pytest
from sqlalchemy import String, create_engine, inspect

from ..secure_objects import SecureObjectRow, ensure_quarantine_table

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_SECURE_OBJECT_HASH_COLUMNS: tuple[str, ...] = (
    "revision_id",
    "previous_revision_id",
    "previous_payload_hash",
    "payload_hash",
    "ciphertext_hash",
)


def _reflected_hash_lengths(table_name: str) -> dict[str, int | None]:
    engine = create_engine("sqlite:///:memory:")
    if table_name == "secure_objects":
        SecureObjectRow.metadata.create_all(engine)
    else:
        ensure_quarantine_table(engine)
    reflected = {column["name"]: column["type"] for column in inspect(engine).get_columns(table_name)}
    lengths: dict[str, int | None] = {}
    for name in _SECURE_OBJECT_HASH_COLUMNS:
        column_type = reflected[name]
        assert isinstance(column_type, String)
        lengths[name] = column_type.length
    engine.dispose()
    return lengths


def test_secure_object_hash_columns_are_reflected_as_fixed_length_varchar() -> None:
    """The live table exposes fixed-width revision/hash metadata."""
    assert _reflected_hash_lengths("secure_objects") == {
        name: 64 for name in _SECURE_OBJECT_HASH_COLUMNS
    }


def test_secure_object_quarantine_preserves_fixed_length_hash_columns() -> None:
    """The quarantine archive mirrors the fixed-width hash metadata contract."""
    assert _reflected_hash_lengths("secure_objects_quarantine") == {
        name: 64 for name in _SECURE_OBJECT_HASH_COLUMNS
    }
