"""Shared support for split adapter tests."""


from __future__ import annotations

import hashlib as hashlib
import logging as logging
import sqlite3 as sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError as ValidationError
from sqlalchemy import event as event

from ......core.classification import SensitivityClass
from ......core.config import Settings
from ... import (
    STORAGE_NAMESPACE_REGISTRY as STORAGE_NAMESPACE_REGISTRY,
)
from ... import (
    WORKFLOW_STATE_NAMESPACE as WORKFLOW_STATE_NAMESPACE,
)
from ... import (
    EphemeralMasterKeyProvider,
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
    StorageHierarchyRegistry as StorageHierarchyRegistry,
)
from ... import (
    StorageNamespaceScope as StorageNamespaceScope,
)
from ...errors import ClassificationError as ClassificationError
from ...errors import StorageValidationError as StorageValidationError
from .._orm import Base
from ..engine import create_engine_from_settings
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
