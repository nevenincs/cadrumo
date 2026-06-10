"""Pointer-file integration tests for the orchestration register / select path.

The orchestration layer's `register_active_profile` and
`select_profile` MUST atomically materialise the plaintext
`<aeat-root>/active-profile` pointer file so a subsequent process
invocation resolves the active profile from disk before any
encrypted state row needs to load. This file pins that contract
end-to-end against a real file-backed storage root, registering each
profile through the production :func:`profile_create_storage_span`
mint path so the pointer write lands inside the sandboxed
active-profile storage root.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....core._bucket_pointer_io import pointer_path, read_pointer
from ....core.config import load_settings
from ....tests.secure_sql import isolated_profile_storage_root
from ...workflow._models import WorkflowState
from .._orchestration import (
    profile_create_storage_span,
    profile_storage_session,
    remove_active_profile,
    select_profile,
)
from .._testing import register_minimal_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _storage_root(tmp_path: Path) -> Iterator[None]:
    """Real file-backed storage root for the production create-span mint path.

    Each profile is registered inside :func:`profile_create_storage_span`,
    which mints the per-bucket wrapped DEK under the resolved file-backend
    master key before :func:`register_active_profile` writes the manifest —
    the genuine ``BUCKET_DEK_V1`` create path, not a legacy no-DEK shortcut.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def test_register_active_profile_writes_pointer_file() -> None:
    """A successful register lands the pointer on disk."""

    with profile_create_storage_span("catering"):
        register_minimal_profile(WorkflowState(), profile_id="catering")

    root = load_settings().aeat_local_storage_root
    pointer = read_pointer(root)
    assert pointer is not None
    assert pointer.bucket_id == "catering"


def test_select_profile_updates_pointer_file() -> None:
    """Switching active profile rewrites the pointer to the new id."""

    state = WorkflowState()
    with profile_create_storage_span("catering"):
        state = register_minimal_profile(state, profile_id="catering")
    with profile_create_storage_span("translation"):
        state = register_minimal_profile(state, profile_id="translation")
    with profile_storage_session("catering"):
        state = select_profile(state, profile_id="catering")

    root = load_settings().aeat_local_storage_root
    pointer = read_pointer(root)
    assert pointer is not None
    assert pointer.bucket_id == "catering"


def test_remove_active_profile_clears_pointer_file() -> None:
    """Tombstoning the active profile unlinks the pointer."""

    state = WorkflowState()
    with profile_create_storage_span("catering"):
        state = register_minimal_profile(state, profile_id="catering")

        root = load_settings().aeat_local_storage_root
        assert read_pointer(root) is not None

        remove_active_profile(state)

    assert not pointer_path(root).exists()
    assert read_pointer(root) is None
