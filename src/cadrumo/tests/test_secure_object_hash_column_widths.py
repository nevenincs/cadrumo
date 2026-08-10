"""Runtime contracts for secure-object hash columns.

The live table and its quarantine archive must agree that revision and hash
metadata is fixed-width: a widened or free-length column would let a truncated
or over-long digest persist, and the digest is what every integrity check keys
on.
"""

from __future__ import annotations

import pytest
from sqlalchemy import String, create_engine, inspect

from ..adapters.persistence.storage.sql import SecureObjectRow, ensure_quarantine_table

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SECURE_OBJECT_HASH_COLUMNS: tuple[str, ...] = (
    "revision_id",
    "previous_revision_id",
    "previous_payload_hash",
    "payload_hash",
    "ciphertext_hash",
)


def test_secure_object_hash_columns_are_reflected_as_fixed_length_varchar() -> None:
    """The live secure_objects table exposes fixed-width revision/hash metadata."""
    engine = create_engine("sqlite:///:memory:")
    SecureObjectRow.metadata.create_all(engine)

    reflected = {column["name"]: column["type"] for column in inspect(engine).get_columns("secure_objects")}

    lengths: dict[str, int | None] = {}
    for name in _SECURE_OBJECT_HASH_COLUMNS:
        column_type = reflected[name]
        assert isinstance(column_type, String)
        lengths[name] = column_type.length
    assert lengths == {name: 64 for name in _SECURE_OBJECT_HASH_COLUMNS}


def test_secure_object_quarantine_preserves_fixed_length_hash_columns() -> None:
    """The quarantine archive mirrors the fixed-width hash metadata contract."""
    engine = create_engine("sqlite:///:memory:")

    ensure_quarantine_table(engine)

    reflected = {column["name"]: column["type"] for column in inspect(engine).get_columns("secure_objects_quarantine")}
    lengths: dict[str, int | None] = {}
    for name in _SECURE_OBJECT_HASH_COLUMNS:
        column_type = reflected[name]
        assert isinstance(column_type, String)
        lengths[name] = column_type.length
    assert lengths == {name: 64 for name in _SECURE_OBJECT_HASH_COLUMNS}
