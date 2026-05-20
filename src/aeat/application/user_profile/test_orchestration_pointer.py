"""Pointer-file integration tests for the orchestration register / select path.

The orchestration layer's `register_active_profile` and
`select_profile` MUST atomically materialise the plaintext
`<aeat-root>/active-profile` pointer file so a subsequent process
invocation resolves the active profile from disk before any
encrypted state row needs to load. This file pins that contract
end-to-end against a real `EphemeralMasterKeyProvider`, real
SQLite, and the canonical `application/conftest.py`
`override_settings(aeat_local_storage_root=tmp_path)` autouse
fixture so the pointer write lands inside the sandbox.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.application.user_profile._orchestration import (
    remove_active_profile,
    select_profile,
)
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow._models import WorkflowState
from aeat.core._bucket_pointer_io import pointer_path, read_pointer
from aeat.core.config import Settings, load_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'orch-pointer.db').as_posix()}"),
        )
        Base.metadata.create_all(engine)
        try:
            yield SecureObjectRepository(engine=engine)
        finally:
            engine.dispose()


def test_register_active_profile_writes_pointer_file(
    secure_objects: SecureObjectRepository,
) -> None:
    """A successful register lands the pointer on disk."""

    register_minimal_profile(WorkflowState(), profile_id="catering", secure_objects=secure_objects)

    root = load_settings().aeat_local_storage_root
    pointer = read_pointer(root)
    assert pointer is not None
    assert pointer.bucket_id == "catering"


def test_select_profile_updates_pointer_file(
    secure_objects: SecureObjectRepository,
) -> None:
    """Switching active profile rewrites the pointer to the new id."""

    state = WorkflowState()
    state = register_minimal_profile(state, profile_id="catering", secure_objects=secure_objects)
    state = register_minimal_profile(state, profile_id="translation", secure_objects=secure_objects)
    state = select_profile(state, profile_id="catering", secure_objects=secure_objects)

    root = load_settings().aeat_local_storage_root
    pointer = read_pointer(root)
    assert pointer is not None
    assert pointer.bucket_id == "catering"


def test_remove_active_profile_clears_pointer_file(
    secure_objects: SecureObjectRepository,
) -> None:
    """Tombstoning the active profile unlinks the pointer."""

    state = register_minimal_profile(WorkflowState(), profile_id="catering", secure_objects=secure_objects)

    root = load_settings().aeat_local_storage_root
    assert read_pointer(root) is not None

    remove_active_profile(state, secure_objects=secure_objects)

    assert not pointer_path(root).exists()
    assert read_pointer(root) is None
