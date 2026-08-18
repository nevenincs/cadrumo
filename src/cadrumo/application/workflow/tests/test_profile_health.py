"""Real current-capsule behaviour for active-profile health and pointer repair."""

from __future__ import annotations

import os
import sys
from base64 import b64encode
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
)
from cadrumo.application.user_profile import (
    profile_bind_bucket_session,
    profile_bucket_session_open_resumed,
    profile_close_bucket_session,
)
from ....application.state_projection import _build_active_profile
from ....application.user_profile import active_profile_pointer_transaction
from ....application.user_profile._capsule_record import ProfileRecordSession
from ....application.user_profile._lifecycle import ProfileCapsuleLifecycle
from ....application.user_profile._profile_record_repository import bound_profile_record_session
from ....core import BucketPointer, read_pointer, write_pointer
from ....core.config import override_settings
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._models import WorkflowState
from .._profile_health import assess_active_profile_health, repair_active_profile_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "31313131-3131-4313-8313-313131313131"
_PROFILE_LABEL = "Operator"
_DEK = bytes(range(32))

_READY_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Test Operator"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def _create_current_profile(*, root: Path, facts: tuple[UserProfileFact, ...] = _READY_FACTS) -> ProfileRecordSession:
    """Publish one real capsule through the production lifecycle owner."""
    identity = UUID(_PROFILE_ID)
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
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=_DEK)
    ProfileCapsuleLifecycle(root=root).create(
        label=_PROFILE_LABEL,
        profile_id=identity,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={},
        initial_record=UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_ID, facts=facts),
        record_session=session,
    )
    return session


def test_active_profile_health_is_ready_from_one_current_capsule_projection(tmp_path: Path) -> None:
    session = _create_current_profile(root=tmp_path)
    try:
        with (
            override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_PROFILE_ID),
            bound_profile_record_session(session),
        ):
            health = assess_active_profile_health(WorkflowState())

        assert health.active_profile == _PROFILE_ID
        assert health.active_profile_label == _PROFILE_LABEL
        assert health.status == "ready"
        assert health.registered_bucket is True
        assert health.profile_record_present is True
        assert health.precondition_verdict is None
        assert _build_active_profile(health).label == _PROFILE_LABEL
        assert "active_profile_label" not in health.model_dump(mode="json")
    finally:
        session.close()


def test_inactive_current_capsule_routes_the_operator_to_login(tmp_path: Path) -> None:
    session = _create_current_profile(root=tmp_path)
    try:
        with active_profile_pointer_transaction(tmp_path) as pointer_transaction:
            pointer_transaction.clear()
        with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
            health = assess_active_profile_health()

        assert health.status == "none"
        assert health.precondition_verdict is not None
        assert health.precondition_verdict.action is not None
        assert health.precondition_verdict.action.action_id == "operator.profile.login"
        assert health.precondition_verdict.missing_argument_names == ("name",)
    finally:
        session.close()


def test_empty_storage_routes_the_operator_to_current_registration(tmp_path: Path) -> None:
    with override_settings(cadrumo_local_storage_root=tmp_path / "empty", cadrumo_active_profile=None):
        health = assess_active_profile_health()

    assert health.status == "none"
    assert health.precondition_verdict is not None
    assert health.precondition_verdict.action is not None
    assert health.precondition_verdict.action.action_id == "operator.profile.create"
    assert health.precondition_verdict.missing_argument_names == ("profile_name",)


def test_pointer_to_no_current_capsule_is_repaired_without_creating_a_bucket(tmp_path: Path) -> None:
    write_pointer(tmp_path, BucketPointer(bucket_id=_PROFILE_ID, schema_version=1))
    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        before = assess_active_profile_health()
        repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

    assert before.status == "dangling_pointer"
    assert before.repairable_by_clearing_pointer is True
    assert repaired.dry_run is False
    assert repaired.cleared_pointer is True
    assert repaired.after is not None
    assert repaired.after.status == "none"
    assert read_pointer(tmp_path) is None


def test_pointer_to_malformed_current_marker_is_reported_as_capsule_integrity_not_manifest_state(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "buckets" / _PROFILE_ID / "profile.commit.v1.json"
    marker.parent.mkdir(parents=True)
    malformed = b"not a current commit"
    marker.write_bytes(malformed)
    write_pointer(tmp_path, BucketPointer(bucket_id=_PROFILE_ID, schema_version=1))

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=None):
        before = assess_active_profile_health()
        repaired = repair_active_profile_pointer(clear_active=True, confirmed=True)

    assert before.status == "capsule_unreadable"
    assert before.repairable_by_clearing_pointer is True
    assert "ProfileCustodyRecordError" in before.profile_record_error
    assert repaired.cleared_pointer is True
    assert repaired.after is not None
    assert repaired.after.status == "capsule_unreadable"
    assert marker.read_bytes() == malformed


def test_health_observes_current_or_degraded_state_without_provider_or_recovery_access(tmp_path: Path) -> None:
    """Observe ready, absent, malformed, and cold state without an implicit unlock.

    The audit hook observes the real process file-access stream after all four
    filesystem arrangements exist.  The secret-store paths are the actual
    configured provider route for each assessment, while the recovery path is
    a deliberately hostile directory inside each current-format custody tree.
    No test double is involved: readiness uses a real, already-authenticated
    custody session and the cold case intentionally has none.
    """
    ready_root = tmp_path / "ready"
    cold_root = tmp_path / "cold"
    absent_root = tmp_path / "absent"
    malformed_root = tmp_path / "malformed"
    ready_record_session = _create_current_profile(root=ready_root)
    cold_record_session = _create_current_profile(root=cold_root)
    ready_record_session.close()
    cold_record_session.close()

    malformed_marker = malformed_root / "buckets" / _PROFILE_ID / "profile.commit.v1.json"
    malformed_marker.parent.mkdir(parents=True)
    malformed_marker.write_bytes(b"malformed current marker")
    write_pointer(malformed_root, BucketPointer(bucket_id=_PROFILE_ID, schema_version=1))

    secret_paths = tuple(root / "secrets" for root in (ready_root, absent_root, malformed_root, cold_root))
    recovery_paths = (
        ready_root / "buckets" / _PROFILE_ID / "custody" / "recovery.v1.json",
        cold_root / "buckets" / _PROFILE_ID / "custody" / "recovery.v1.json",
        malformed_root / "buckets" / _PROFILE_ID / "custody" / "recovery.v1.json",
    )
    for path in (*secret_paths, *recovery_paths):
        path.mkdir(parents=True, exist_ok=True)

    sensitive_accesses: list[str] = []

    def observe_open(event: str, arguments: tuple[object, ...]) -> None:
        if event != "open" or not arguments:
            return
        candidate = arguments[0]
        if not isinstance(candidate, (str, bytes, os.PathLike)):
            return
        candidate_text = os.fsdecode(os.fspath(candidate))
        candidate_path = Path(candidate_text)
        if candidate_path in recovery_paths or any(
            candidate_path == secret_path or secret_path in candidate_path.parents for secret_path in secret_paths
        ):
            sensitive_accesses.append(candidate_text)

    def observe_filesystem_calls(frame: object, event: str, argument: object) -> None:
        if event != "c_call" or getattr(argument, "__name__", "") not in {"stat", "lstat", "open", "read"}:
            return
        local_values = getattr(frame, "f_locals", {}).values()
        watched_paths = (*secret_paths, *recovery_paths)
        if any(isinstance(value, Path) and value in watched_paths for value in local_values):
            sensitive_accesses.append(getattr(argument, "__name__", "unknown"))

    sys.addaudithook(observe_open)
    previous_profile = sys.getprofile()
    sys.setprofile(observe_filesystem_calls)
    instant = datetime.now(UTC)
    ready_custody_session = profile_bucket_session_open_resumed(
        bucket_id=_PROFILE_ID,
        dek=_DEK,
        idle_minutes=15,
        opened_at=instant,
        idle_deadline=instant + timedelta(minutes=15),
        absolute_deadline=instant + timedelta(hours=4),
        storage_root=ready_root,
    )
    try:
        profile_bind_bucket_session(ready_custody_session)
        with override_settings(
            cadrumo_local_storage_root=ready_root,
            cadrumo_secret_store_dir=ready_root / "secrets",
            cadrumo_active_profile=_PROFILE_ID,
        ):
            ready = assess_active_profile_health()
        profile_close_bucket_session()

        with override_settings(
            cadrumo_local_storage_root=absent_root,
            cadrumo_secret_store_dir=absent_root / "secrets",
            cadrumo_active_profile=None,
        ):
            absent = assess_active_profile_health()
        with override_settings(
            cadrumo_local_storage_root=malformed_root,
            cadrumo_secret_store_dir=malformed_root / "secrets",
            cadrumo_active_profile=None,
        ):
            malformed = assess_active_profile_health()
        with override_settings(
            cadrumo_local_storage_root=cold_root,
            cadrumo_secret_store_dir=cold_root / "secrets",
            cadrumo_active_profile=_PROFILE_ID,
        ):
            cold = assess_active_profile_health()
    finally:
        profile_close_bucket_session()
        sys.setprofile(previous_profile)

    assert ready.status == "ready"
    assert absent.status == "none"
    assert malformed.status == "capsule_unreadable"
    assert cold.status == "profile_record_unreadable"
    assert cold.precondition_verdict is not None
    assert cold.precondition_verdict.failed_condition_id == "profile.active.record_readable"
    assert sensitive_accesses == []
