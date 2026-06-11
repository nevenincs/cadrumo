"""Shared support for split adapter tests."""


from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ......core.classification import SensitivityClass
from ......core.config import Settings
from ... import EphemeralMasterKeyProvider
from .._orm import Base
from ..engine import create_engine_from_settings
from ..secure_objects import (
    SecureObjectRepository,
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
