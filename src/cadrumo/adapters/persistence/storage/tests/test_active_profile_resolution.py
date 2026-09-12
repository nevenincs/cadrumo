"""Real-capsule active-profile resolution and custody refusal tests."""

from __future__ import annotations

from base64 import b64encode
from pathlib import Path
from uuid import UUID

import pytest

from .....adapters.persistence.storage.custody.errors import ProfileCustodyRefusal, ProfileCustodyRefusedError
from .....adapters.persistence.storage.custody.records import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
)
from .....adapters.persistence.storage.custody.sentinel import create_profile_custody_sentinel
from .....application.user_profile.capsule_record import ProfileRecordSession
from .....application.user_profile.custody_transactions import ProfileCustodyTransactionConflictError
from .....application.user_profile.lifecycle import ProfileCapsuleLifecycle
from .....application.user_profile.profile_record_repository import bound_profile_record_session
from .....application.workflow.profile_bucket_scan import resolve_profile_bucket
from .....application.workflow.profile_health import assess_active_profile_health, repair_active_profile_pointer
from .....application.workflow.state_models import WorkflowState
from .....core.bucket_pointer import BucketPointer, pointer_path, read_pointer, write_pointer
from .....core.config import override_settings
from .....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from .....tests.profile_capsule import mint_test_profile_recovery_envelope

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_DEK = bytes(range(32))


def _current_profile_session(profile_id: str, *, root: Path, label: str) -> ProfileRecordSession:
    """Create one real committed current capsule and return its live record session."""
    identity = UUID(profile_id)
    seed = identity.bytes + identity.bytes
    envelope = ProfileCustodyEnvelope.create(
        profile_id=identity,
        password_generation=1,
        dek_epoch=b64encode(seed[:16]).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(seed[16:]).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(seed[:12]).decode("ascii"),
            ciphertext_b64=b64encode(seed).decode("ascii"),
            tag_b64=b64encode(seed[:16]).decode("ascii"),
        ),
    )
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=_PROFILE_DEK)
    ProfileCapsuleLifecycle(root=root).create(
        label=label,
        profile_id=identity,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_PROFILE_DEK),
        data_files={},
        recovery_envelope=mint_test_profile_recovery_envelope(
            identity,
            dek=_PROFILE_DEK,
            dek_epoch=envelope.dek_epoch,
        ),
        initial_record=UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=str(identity),
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        ),
        record_session=session,
    )
    return session


def test_label_override_resolves_real_record_and_masks_dangling_pointer_repair(tmp_path: Path) -> None:
    """Canonicalize an override label before secure reads while preserving pointer precedence."""

    bucket_id = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    dangling_id = "62d2ab08-39f2-4811-bd2a-fe48fd105e4a"
    session = _current_profile_session(bucket_id, root=tmp_path, label="Operator")
    try:
        write_pointer(tmp_path, BucketPointer.selected(bucket_id=dangling_id, transition_revision=1))
        target = pointer_path(tmp_path)
        dangling_bytes = target.read_bytes()

        with (
            override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile="operator"),
            bound_profile_record_session(session),
        ):
            state = WorkflowState()
            assert state.active_profile_bucket_id() == bucket_id
            assert state.active_profile_record() is not None

            protected_health = assess_active_profile_health(state)

            assert protected_health.active_profile == bucket_id
            assert protected_health.source == "env_override"
            assert protected_health.status == "incomplete"
            assert protected_health.registered_bucket is True
            assert protected_health.profile_record_present is True
            assert protected_health.repairable_by_clearing_pointer is False
            assert target.read_bytes() == dangling_bytes

        with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
            exposed_health = assess_active_profile_health()
            repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

        assert exposed_health.active_profile == dangling_id
        assert exposed_health.source == "pointer"
        assert exposed_health.status == "dangling_pointer"
        assert exposed_health.repairable_by_clearing_pointer is True
        assert repaired.before == exposed_health
        assert repaired.dry_run is False
        assert repaired.cleared_pointer is True
        assert repaired.after is not None
        assert repaired.after.status == "none"
        assert read_pointer(tmp_path).bucket_id is None
    finally:
        session.close()


def test_resolve_profile_bucket_refuses_a_retired_manifest_without_reading_it(tmp_path: Path) -> None:
    """A retired manifest is a typed custody refusal, not an alternate discovery route."""
    retired = tmp_path / "buckets" / "51c1fa97-28e1-4700-ac1e-ed7cf094d37b" / "manifest.toml"
    retired.parent.mkdir(parents=True)
    retired.write_bytes(b"this retired document is deliberately malformed")

    with pytest.raises(ProfileCustodyRefusedError) as captured:
        resolve_profile_bucket("operator", root=tmp_path)

    assert captured.value.refusal is ProfileCustodyRefusal.LEGACY_CUSTODY_DETECTED


def test_resolve_profile_bucket_resolves_an_active_profile_by_display_name(tmp_path: Path) -> None:
    """A display-name identifier resolves to the UUID bucket via the label fallback."""

    uuid = "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
    session = _current_profile_session(uuid, root=tmp_path, label="operator")
    session.close()

    pointer = resolve_profile_bucket("operator", root=tmp_path)

    assert pointer is not None
    assert pointer.bucket_id == uuid, "the display name must resolve to the immutable UUID bucket id"
    assert pointer.label == "operator"


def test_resolve_profile_bucket_returns_none_for_an_unknown_identifier(tmp_path: Path) -> None:
    """Neither a UUID-shaped nor a label-shaped unknown identifier resolves."""

    session = _current_profile_session(
        "51c1fa97-28e1-4700-ac1e-ed7cf094d37b",
        root=tmp_path,
        label="operator",
    )
    session.close()

    assert resolve_profile_bucket("nonexistent", root=tmp_path) is None


def test_duplicate_label_is_refused_before_a_second_capsule_can_enter_discovery(tmp_path: Path) -> None:
    """Current projections never carry a legacy ambiguous-label state."""
    first = _current_profile_session(
        "51c1fa97-28e1-4700-ac1e-ed7cf094d37b",
        root=tmp_path,
        label="operator",
    )
    first.close()

    with pytest.raises(ProfileCustodyTransactionConflictError):
        _current_profile_session(
            "62d2ab08-39f2-4811-bd2a-fe48fd105e4a",
            root=tmp_path,
            label="operator",
        )

    resolved = resolve_profile_bucket("operator", root=tmp_path)
    assert resolved is not None
    assert resolved.bucket_id == "51c1fa97-28e1-4700-ac1e-ed7cf094d37b"
