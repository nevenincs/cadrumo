"""Shared support for split adapter tests."""

from __future__ import annotations

import hashlib as hashlib
import logging as logging
import sqlite3 as sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError as ValidationError
from sqlalchemy import event as event

from ......core.classification import SensitivityClass
from ......tests.master_key import EphemeralMasterKeyProvider
from ... import (
    STORAGE_NAMESPACE_REGISTRY as STORAGE_NAMESPACE_REGISTRY,
)
from ... import (
    WORKFLOW_STATE_NAMESPACE as WORKFLOW_STATE_NAMESPACE,
)
from ... import (
    SecureObjectNamespaceDefinition as SecureObjectNamespaceDefinition,
)
from ... import (
    SecureObjectNamespaceIntegrity as SecureObjectNamespaceIntegrity,
)
from ... import (
    SecureObjectWrite as SecureObjectWrite,
)
from ... import (
    StorageCustodyDisposition as StorageCustodyDisposition,
)
from ... import (
    StorageHierarchyRegistry as StorageHierarchyRegistry,
)
from ... import (
    StorageNamespaceScope as StorageNamespaceScope,
)
from ...errors import ClassificationError as ClassificationError
from ...errors import StorageValidationError as StorageValidationError
from ...tests.engine_bootstrap import bootstrap_sqlite_engine
from ..secure_objects import (
    EnvelopeVersionError as EnvelopeVersionError,
)
from ..secure_objects import (
    SecureObjectRecord as SecureObjectRecord,
)
from ..secure_objects import (
    SecureObjectRepository,
)
from ..secure_objects import (
    SecureObjectRevisionConflictError as SecureObjectRevisionConflictError,
)
from ..secure_objects import (
    SecureObjectUnreadable as SecureObjectUnreadable,
)
from ..secure_objects import (
    SecureObjectUnreadableError as SecureObjectUnreadableError,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@contextmanager
def _ephemeral_secure_repo_at(
    db_path: Path,
) -> Iterator[tuple[Any, SecureObjectRepository]]:
    """Open ``db_path`` under a fresh, self-managed ephemeral key.

    This is intentionally distinct from :func:`_repo_at`: callers of the
    latter already own an active :class:`EphemeralMasterKeyProvider`, while
    this helper owns the provider lifecycle for a fresh-key reopen.
    """
    with EphemeralMasterKeyProvider():
        engine = bootstrap_sqlite_engine(db_path)
        try:
            yield engine, SecureObjectRepository(engine=engine)
        finally:
            engine.dispose()


@contextmanager
def _ephemeral_secure_repo(
    tmp_path: Path,
    database_name: str,
) -> Iterator[tuple[Path, Any, SecureObjectRepository]]:
    """Open a filename-derived repository under a fresh ephemeral key.

    Yields ``(db_path, engine, repo)`` so callers can inspect the raw engine
    or reopen the same on-disk database under the same key.
    """
    db_path = tmp_path / database_name
    with _ephemeral_secure_repo_at(db_path) as (engine, repo):
        yield db_path, engine, repo


@contextmanager
def _repo_at(db_path: Path) -> Iterator[SecureObjectRepository]:
    """Open a real :class:`SecureObjectRepository` against a fresh schema at ``db_path``."""
    engine = bootstrap_sqlite_engine(db_path)
    try:
        yield SecureObjectRepository(engine=engine)
    finally:
        engine.dispose()


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
        engine = bootstrap_sqlite_engine(db_path)
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
