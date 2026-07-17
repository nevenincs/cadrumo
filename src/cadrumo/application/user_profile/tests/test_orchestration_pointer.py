"""Pointer-file integration tests for the orchestration register / select path.

The orchestration layer's `register_active_profile` and
`select_profile` MUST atomically materialise the plaintext
`<cadrumo-root>/active-profile` pointer file so a subsequent process
invocation resolves the active profile from disk before any
encrypted state row needs to load. This file pins that contract
end-to-end against a real file-backed storage root, registering each
profile through the production :func:`profile_create_storage_span`
mint path so the pointer write lands inside the sandboxed
active-profile storage root.
"""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event

import pytest

from ....adapters.persistence.storage import LockAcquisitionError
from ....adapters.persistence.storage.bucket import (
    BucketKeySchedule,
    BucketManifest,
    manifest_path,
    provision_bucket_directory,
    write_manifest,
)
from ....adapters.persistence.storage.master_key import KdfParams
from ....core import BucketPointer, capture_pointer, pointer_path, read_pointer, restore_pointer, write_pointer
from ....core.config import load_settings, override_settings
from ....domain.user_profile import ProfileSchemaValidationError, UserProfileStatus
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ... import wizard as _wizard  # noqa: F401
from ...workflow import WorkflowState, repair_active_profile_pointer
from .. import ProfileRepository, active_profile_pointer_transaction
from .._orchestration import (
    profile_create_storage_span,
    profile_storage_session,
    remove_active_profile,
    select_profile,
)

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

    with profile_create_storage_span("12121212-1212-4121-8121-121212121212"):
        register_minimal_profile(WorkflowState(), profile_id="12121212-1212-4121-8121-121212121212")

    root = load_settings().cadrumo_local_storage_root
    pointer = read_pointer(root)
    assert pointer is not None
    assert pointer.bucket_id == "12121212-1212-4121-8121-121212121212"


def test_select_profile_updates_pointer_file() -> None:
    """Switching active profile rewrites the pointer to the new id."""

    state = WorkflowState()
    with profile_create_storage_span("12121212-1212-4121-8121-121212121212"):
        state = register_minimal_profile(state, profile_id="12121212-1212-4121-8121-121212121212")
    with profile_create_storage_span("13131313-1313-4131-8131-131313131313"):
        state = register_minimal_profile(state, profile_id="13131313-1313-4131-8131-131313131313")
    with profile_storage_session("12121212-1212-4121-8121-121212121212"):
        state = select_profile(state, profile_id="12121212-1212-4121-8121-121212121212")

    root = load_settings().cadrumo_local_storage_root
    pointer = read_pointer(root)
    assert pointer is not None
    assert pointer.bucket_id == "12121212-1212-4121-8121-121212121212"


def test_remove_active_profile_clears_pointer_file() -> None:
    """Tombstoning the active profile unlinks the pointer."""

    state = WorkflowState()
    with profile_create_storage_span("12121212-1212-4121-8121-121212121212"):
        state = register_minimal_profile(state, profile_id="12121212-1212-4121-8121-121212121212")

        root = load_settings().cadrumo_local_storage_root
        assert read_pointer(root) is not None

        remove_active_profile(state)

    assert not pointer_path(root).exists()
    assert read_pointer(root) is None


def test_repository_failed_create_restores_exact_pointer_bytes_under_outer_ownership() -> None:
    survivor_id = "14141414-1414-4141-8141-141414141414"
    victim_id = "15151515-1515-4151-8151-151515151515"

    with profile_create_storage_span(survivor_id):
        register_minimal_profile(WorkflowState(), profile_id=survivor_id)
    with profile_create_storage_span(victim_id):
        pass

    root = load_settings().cadrumo_local_storage_root
    victim_paths = provision_bucket_directory(root, victim_id)
    write_manifest(
        victim_paths,
        BucketManifest(
            bucket_id=victim_id,
            label="Victim session setup",
            created_at=datetime.now(UTC).replace(microsecond=0),
            last_unlocked_at=None,
            kdf_params=KdfParams.default().to_manifest_params(),
            recovery_enrolled=False,
            key_schedule=BucketKeySchedule.BUCKET_DEK_V1,
            schema_version=2,
            status=UserProfileStatus.ACTIVE,
        ),
    )
    survivor_pointer_bytes = f'# retained survivor\r\nschema_version = 1\r\nbucket_id = "{survivor_id}"\r\n'.encode()
    restore_pointer(root, survivor_pointer_bytes)
    assert capture_pointer(root) == survivor_pointer_bytes
    assert read_pointer(root) == BucketPointer(bucket_id=survivor_id, schema_version=1)

    with active_profile_pointer_transaction(root) as pointer_transaction, profile_storage_session(victim_id):
        manifest_path(victim_paths).unlink()
        with pytest.raises(ProfileSchemaValidationError):
            ProfileRepository(root=root).create(
                label="Rejected victim",
                facts=(),
                profile_id=victim_id,
                routing_profile_id=victim_id,
                enforce_unique_tax_id=False,
            )
        assert pointer_transaction.capture() == survivor_pointer_bytes

    assert capture_pointer(root) == survivor_pointer_bytes
    assert manifest_path(victim_paths).exists() is False
    assert victim_paths.bucket_dir.exists() is False
    with profile_storage_session(survivor_id):
        survivor = ProfileRepository(root=root).load(survivor_id)
    assert survivor.profile_id == survivor_id


def test_dangling_pointer_repair_fails_closed_under_thread_contention_then_retries() -> None:
    dangling_id = "16161616-1616-4161-8161-161616161616"
    root = load_settings().cadrumo_local_storage_root
    write_pointer(root, BucketPointer(bucket_id=dangling_id, schema_version=1))
    dangling_pointer_bytes = capture_pointer(root)
    assert dangling_pointer_bytes is not None

    acquired = Event()
    release = Event()

    def hold_pointer_transaction() -> None:
        with active_profile_pointer_transaction(root):
            acquired.set()
            if not release.wait(timeout=10.0):
                raise TimeoutError("pointer transaction release handshake timed out")

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(hold_pointer_transaction)
    try:
        assert acquired.wait(timeout=10.0), "worker did not acquire the pointer transaction"
        with override_settings(
            cadrumo_active_profile=None,
            cadrumo_file_lock_timeout_s=0.05,
            cadrumo_file_lock_retry_backoff_s=0.01,
        ):
            with pytest.raises(LockAcquisitionError):
                repair_active_profile_pointer(clear_active=True, confirmed=True)
            assert capture_pointer(root) == dangling_pointer_bytes
    finally:
        release.set()
        future.result(timeout=10.0)
        executor.shutdown(wait=True)

    with override_settings(
        cadrumo_active_profile=None,
        cadrumo_file_lock_timeout_s=0.05,
        cadrumo_file_lock_retry_backoff_s=0.01,
    ):
        repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

    assert repaired.before.status == "dangling_pointer"
    assert repaired.before.source == "pointer"
    assert repaired.dry_run is False
    assert repaired.cleared_pointer is True
    assert repaired.after is not None
    assert repaired.after.status == "none"
    assert capture_pointer(root) is None
