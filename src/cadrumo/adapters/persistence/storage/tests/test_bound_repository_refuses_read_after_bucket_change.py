"""A repository pinned to one bucket refuses READS once the session moves.

Four sibling tests in ``test_runtime.py`` prove a bound repository refuses
after the active session changes bucket: a write, a raw-key write, a
quarantine, a diagnostics pass. Read was not among them, and read is the one
direction where a regression LEAKS rather than loses.

The asymmetry matters because the two failures do not look alike. A write that
escapes the guard lands a row in the wrong bucket -- wrong, loud, and
eventually visible as data that does not belong. A read that escapes returns
one profile's decrypted records to an operator who believes they are in
another, into whatever payload, log line or export that operator is composing.
Nothing about the value announces which profile it came from.

The guard is one method, ``_require_active_session_for_bucket``, shared by
every operation, so today the read path is protected by construction. That is
exactly why it is worth pinning: the shared method makes the protection
invisible at the call site, and reads are the hot path most likely to be
"optimised" past a check that looks redundant.

Asserted with a payload that is unique to the source bucket, so a leak is
identifiable as a leak rather than inferred from an absence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from .....core.config import Settings, override_settings
from .._secure_object_namespaces import WORKFLOW_STATE_NAMESPACE
from .._runtime_readiness import StorageRuntimeReadinessCode
from ..errors import StorageValidationError
from ..master_key import BucketSession, activate_session
from ..runtime import inspect_storage_runtime
from .registered_bucket import publish_registration_capsule

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NOW = datetime(2099, 5, 26, 12, 15, 0, tzinfo=UTC)
_BUCKET_A_ID = "094d94e7-4474-407c-8971-d9c1a2476db0"
_BUCKET_B_ID = "d9df0562-55c9-43c8-8486-b79d4016cfbc"
_A_ONLY_PAYLOAD = b"payload-that-exists-only-in-bucket-a"


def _session(bucket_id: str) -> BucketSession:
    """Open a real session for ``bucket_id``."""
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=30,
        opened_at=_NOW,
        storage_root=None,
    )


def test_a_bound_repository_refuses_to_read_once_the_session_serves_another_bucket(
    tmp_path: Path,
) -> None:
    """DISCRIMINATING: the direction that would hand B's operator A's records."""
    for identity in (_BUCKET_A_ID, _BUCKET_B_ID):
        publish_registration_capsule(tmp_path, identity)
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_A_ID)
    namespace = WORKFLOW_STATE_NAMESPACE.namespace

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        activate_session(_session(_BUCKET_A_ID)),
    ):
        repository = inspect_storage_runtime(settings, now=_NOW).secure_object_repository()
        repository.save(
            namespace=namespace,
            object_key="state",
            classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
            schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=_A_ONLY_PAYLOAD,
        )

        with activate_session(_session(_BUCKET_B_ID)), pytest.raises(StorageValidationError) as raised:
            repository.load(
                namespace,
                "state",
                expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
                max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
            )

    assert raised.value.translated_message == "errors.storage.runtime.not_ready"
    assert StorageRuntimeReadinessCode.SESSION_CHANGED.value in str(raised.value.context)


def test_the_same_repository_still_reads_under_its_own_bucket(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: the refusal must be the bucket change, not a broken read.

    Without this, a repository that had stopped reading for any reason at all
    -- a closed engine, a mis-set namespace, a fixture that never wrote --
    would satisfy the assertion above while proving nothing about isolation.
    The payload asserted here is the one the leak test looks for.
    """
    publish_registration_capsule(tmp_path, _BUCKET_A_ID)
    settings = Settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_A_ID)
    namespace = WORKFLOW_STATE_NAMESPACE.namespace

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        activate_session(_session(_BUCKET_A_ID)),
    ):
        repository = inspect_storage_runtime(settings, now=_NOW).secure_object_repository()
        repository.save(
            namespace=namespace,
            object_key="state",
            classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
            schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
            written_at=_NOW,
            payload=_A_ONLY_PAYLOAD,
        )
        loaded = repository.load(
            namespace,
            "state",
            expected_class=WORKFLOW_STATE_NAMESPACE.sensitivity,
            max_supported_version=WORKFLOW_STATE_NAMESPACE.schema_version,
        )

    assert loaded is not None
    assert loaded.payload == _A_ONLY_PAYLOAD
