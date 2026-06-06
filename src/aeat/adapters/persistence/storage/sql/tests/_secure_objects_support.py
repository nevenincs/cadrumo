"""Shared support for split adapter tests."""

# ruff: noqa: F401

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import event

from ......core.classification import SensitivityClass
from ......core.config import Settings
from ... import EphemeralMasterKeyProvider
from ..._namespace_registry import (
    STORAGE_NAMESPACE_REGISTRY,
    WORKFLOW_STATE_NAMESPACE,
    SecureObjectNamespaceDefinition,
    StorageHierarchyRegistry,
    StorageNamespaceScope,
)
from ...crypto._encrypted_columns import EncryptedBytes, EncryptedString
from ...errors import (
    ClassificationError,
    EnvelopeVersionError,
    SecureObjectRevisionConflictError,
    SecureObjectUnreadableError,
    StorageValidationError,
)
from .._orm import Base, SecureObjectRow
from ..engine import create_engine_from_settings
from ..secure_objects import (
    SecureObjectNamespaceIntegrity,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectUnreadable,
    SecureObjectWrite,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

def _create_legacy_secure_objects_table(engine) -> None:
    """Create the pre-HashedLookup secure_objects table shape."""
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE secure_objects ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "namespace VARCHAR(128) NOT NULL, "
            "object_key BLOB NOT NULL, "
            "classification VARCHAR(32) NOT NULL, "
            "schema_version INTEGER NOT NULL, "
            "written_at DATETIME NOT NULL, "
            "payload BLOB NOT NULL, "
            "CONSTRAINT uq_secure_objects_identity UNIQUE (namespace, object_key)"
            ")"
        )

def _seed_legacy_encrypted_string_key_row(
    engine,
    *,
    namespace: str,
    natural_key: str,
    classification: SensitivityClass,
    schema_version: int,
    written_at: datetime,
    payload: bytes,
) -> None:
    """Insert a row as the old mapper did: randomized encrypted key + encrypted payload."""
    object_key = EncryptedString().process_bind_param(natural_key, engine.dialect)
    payload_wire = EncryptedBytes().process_bind_param(payload, engine.dialect)
    assert object_key is not None
    assert payload_wire is not None
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO secure_objects "
            "(namespace, object_key, classification, schema_version, written_at, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                namespace,
                object_key,
                classification.value,
                schema_version,
                written_at,
                payload_wire,
            ),
        )

def _seed_under_key(
    *,
    db_path: Path,
    provider: EphemeralMasterKeyProvider,
    namespace: str,
    natural_key: str,
    payload: bytes,
) -> None:
    """Seed one secure-object row through the public repository under ``provider``."""
    with provider:
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            SecureObjectRepository(engine=engine).save(
                namespace=namespace,
                object_key=natural_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=payload,
            )
        finally:
            engine.dispose()
