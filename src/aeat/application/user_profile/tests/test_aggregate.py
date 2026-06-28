"""Unit tests for :class:`ProfileAggregate` and :func:`verify_profile_integrity`.

The aggregate is the whole-profile in-memory object; its
model-validator rejects an aggregate whose projections disagree on
identity. :func:`verify_profile_integrity` is the read-time gate the
repository runs before the aggregate is even constructed. Both are the
structural defence against the ghost-profile / ``missing_profile_record``
defect class.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....adapters.persistence.storage.bucket._manifest import (
    BucketLifecycleStatus,
    ManifestKdfParams,
)
from ....domain.user_profile import UserProfileRecord, UserProfileStatus
from .._aggregate import ProfileAggregate
from .._integrity import ProfileIntegrityError, verify_profile_integrity

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_UUID = "c7f3a1b2-9d4e-4a5f-8b6c-1e2d3f4a5b6c"


def _kdf_params() -> ManifestKdfParams:
    return ManifestKdfParams(
        algorithm="argon2id",
        version=0x13,
        memory_cost=19_456,
        time_cost=2,
        parallelism=1,
        salt=b"0123456789abcdef",
        output_length=32,
    )


def _record(
    profile_id: str = _PROFILE_UUID,
    *,
    status: UserProfileStatus = UserProfileStatus.ACTIVE,
) -> UserProfileRecord:
    now = datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC)
    record = UserProfileRecord(
        profile_id=profile_id,
        display_name="Aggregate Operator",
        created_at=now,
        updated_at=now,
    )
    if status is UserProfileStatus.TOMBSTONED:
        return record.tombstone()
    return record


def test_aggregate_accepts_consistent_projections() -> None:
    """An aggregate whose stores all agree on identity is constructed."""

    record = _record()
    aggregate = ProfileAggregate(
        profile_id=_PROFILE_UUID,
        label="Aggregate Operator",
        created_at=datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC),
        kdf_params=_kdf_params(),
        recovery_enrolled=False,
        manifest_schema_version=1,
        record=record,
        status=UserProfileStatus.ACTIVE,
    )
    assert aggregate.profile_id == _PROFILE_UUID
    assert aggregate.record is record


def _assert_validation_error_redacts(error: ValidationError, *sensitive_tokens: str) -> None:
    rendered = str(error)
    assert "profile aggregate projections are inconsistent" in rendered
    for token in sensitive_tokens:
        assert token not in rendered


def test_aggregate_rejects_record_profile_id_mismatch() -> None:
    """An aggregate whose record carries a different UUID is rejected."""

    mismatched_profile_id = "00000000-0000-4000-8000-000000000000"
    with pytest.raises(ValidationError) as exc_info:
        ProfileAggregate(
            profile_id=_PROFILE_UUID,
            label="Aggregate Operator",
            created_at=datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC),
            kdf_params=_kdf_params(),
            recovery_enrolled=False,
            manifest_schema_version=1,
            record=_record(mismatched_profile_id),
            status=UserProfileStatus.ACTIVE,
        )
    _assert_validation_error_redacts(exc_info.value, _PROFILE_UUID, mismatched_profile_id, "Aggregate Operator")


def test_aggregate_rejects_torn_rename_label_mismatch() -> None:
    """A torn rename — label disagreeing with record.display_name — is caught.

    A rename writes the new name into the plaintext manifest and the
    encrypted record's ``display_name`` as two sequential store
    writes. A crash between them leaves the manifest carrying the new
    label while the record still holds the old ``display_name`` (or
    vice versa). The aggregate's cross-store agreement validator must
    refuse to construct an aggregate over that torn state rather than
    silently serve a profile whose two stores disagree on its name.
    """

    record = _record()  # record.display_name == "Aggregate Operator"
    with pytest.raises(ValidationError) as exc_info:
        ProfileAggregate(
            profile_id=_PROFILE_UUID,
            label="Renamed Operator",
            created_at=datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC),
            kdf_params=_kdf_params(),
            recovery_enrolled=False,
            manifest_schema_version=1,
            record=record,
            status=UserProfileStatus.ACTIVE,
        )
    _assert_validation_error_redacts(exc_info.value, _PROFILE_UUID, "Renamed Operator", "Aggregate Operator")


def test_aggregate_rejects_status_mismatch() -> None:
    """An aggregate whose status disagrees with the record is rejected."""

    with pytest.raises(ValidationError) as exc_info:
        ProfileAggregate(
            profile_id=_PROFILE_UUID,
            label="Aggregate Operator",
            created_at=datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC),
            kdf_params=_kdf_params(),
            recovery_enrolled=False,
            manifest_schema_version=1,
            record=_record(status=UserProfileStatus.TOMBSTONED),
            status=UserProfileStatus.ACTIVE,
        )
    _assert_validation_error_redacts(exc_info.value, _PROFILE_UUID, "Aggregate Operator")


def test_verify_integrity_passes_when_every_store_agrees() -> None:
    """No exception when directory, manifest, and record agree."""

    verify_profile_integrity(
        profile_id=_PROFILE_UUID,
        directory_name=_PROFILE_UUID,
        manifest_bucket_id=_PROFILE_UUID,
        record_profile_id=_PROFILE_UUID,
        manifest_status="active",
        record_status="active",
        manifest_label="Aggregate Operator",
        record_display_name="Aggregate Operator",
    )


def _assert_integrity_error_redacts(
    error: ProfileIntegrityError,
    *,
    message: str,
    translated_message: str,
    sensitive_tokens: tuple[str, ...],
) -> None:
    rendered = str(error)
    assert rendered == message
    assert error.translated_message == translated_message
    for token in sensitive_tokens:
        assert token not in rendered


def test_verify_integrity_raises_on_manifest_drift() -> None:
    """A manifest bucket_id that disagrees raises ProfileIntegrityError."""

    mismatched_bucket_id = "00000000-0000-4000-8000-000000000000"
    with pytest.raises(ProfileIntegrityError) as exc_info:
        verify_profile_integrity(
            profile_id=_PROFILE_UUID,
            directory_name=_PROFILE_UUID,
            manifest_bucket_id=mismatched_bucket_id,
            record_profile_id=_PROFILE_UUID,
            manifest_status="active",
            record_status="active",
            manifest_label="Aggregate Operator",
            record_display_name="Aggregate Operator",
        )
    error = exc_info.value
    assert error.context == {"mismatches": ("manifest_bucket_id",)}
    _assert_integrity_error_redacts(
        error,
        message="profile physical stores disagree on identity",
        translated_message="application.user_profile.errors.profile_integrity_identity_mismatch",
        sensitive_tokens=(_PROFILE_UUID, mismatched_bucket_id),
    )


def test_verify_integrity_raises_on_record_drift() -> None:
    """A record profile_id that disagrees raises ProfileIntegrityError."""

    mismatched_record_id = "00000000-0000-4000-8000-000000000000"
    with pytest.raises(ProfileIntegrityError) as exc_info:
        verify_profile_integrity(
            profile_id=_PROFILE_UUID,
            directory_name=_PROFILE_UUID,
            manifest_bucket_id=_PROFILE_UUID,
            record_profile_id=mismatched_record_id,
            manifest_status="active",
            record_status="active",
            manifest_label="Aggregate Operator",
            record_display_name="Aggregate Operator",
        )
    error = exc_info.value
    assert error.context == {"mismatches": ("secure_record_profile_id",)}
    _assert_integrity_error_redacts(
        error,
        message="profile physical stores disagree on identity",
        translated_message="application.user_profile.errors.profile_integrity_identity_mismatch",
        sensitive_tokens=(_PROFILE_UUID, mismatched_record_id),
    )


def test_lifecycle_status_enums_stay_value_synced() -> None:
    """``BucketLifecycleStatus`` and ``UserProfileStatus`` carry the same values.

    The plaintext manifest mirrors the encrypted record's lifecycle
    status; ``_manifest_status_for`` maps the two enums by string
    value, and ``verify_profile_integrity`` compares them by value. A
    state added to one enum but not the other would silently break
    that mapping — this guard fails the moment the two diverge.
    """

    assert {member.value for member in UserProfileStatus} == {member.value for member in BucketLifecycleStatus}


def test_verify_integrity_raises_on_lifecycle_status_drift() -> None:
    """A manifest status that disagrees with the record status raises.

    A manifest saying ``active`` over a tombstoned record is the drift
    state that re-opens the tombstone leak; the integrity gate must
    surface it rather than serve the profile.
    """

    with pytest.raises(ProfileIntegrityError) as exc_info:
        verify_profile_integrity(
            profile_id=_PROFILE_UUID,
            directory_name=_PROFILE_UUID,
            manifest_bucket_id=_PROFILE_UUID,
            record_profile_id=_PROFILE_UUID,
            manifest_status="active",
            record_status="tombstoned",
            manifest_label="Aggregate Operator",
            record_display_name="Aggregate Operator",
        )
    error = exc_info.value
    assert error.context == {"mismatches": ("manifest_status", "secure_record_status")}
    _assert_integrity_error_redacts(
        error,
        message="profile physical stores disagree on lifecycle status",
        translated_message="application.user_profile.errors.profile_integrity_status_mismatch",
        sensitive_tokens=(_PROFILE_UUID, "active", "tombstoned"),
    )


def test_verify_integrity_raises_on_label_drift() -> None:
    """A manifest label that disagrees with the record display name raises.

    A crash between the two sequential rename writes leaves the manifest and the
    record holding different labels. The read-time integrity gate surfaces that
    drift as a ``ProfileIntegrityError`` (the same way it surfaces status drift),
    so the repository never serves a profile whose two stores disagree on its
    name. ``ProfileAggregate`` enforces the same agreement one layer later; this
    gate makes the refusal happen at the documented integrity boundary.
    """

    with pytest.raises(ProfileIntegrityError) as exc_info:
        verify_profile_integrity(
            profile_id=_PROFILE_UUID,
            directory_name=_PROFILE_UUID,
            manifest_bucket_id=_PROFILE_UUID,
            record_profile_id=_PROFILE_UUID,
            manifest_status="active",
            record_status="active",
            manifest_label="Renamed Operator",
            record_display_name="Aggregate Operator",
        )
    error = exc_info.value
    assert error.context == {"mismatches": ("manifest_label", "secure_record_display_name")}
    _assert_integrity_error_redacts(
        error,
        message="profile physical stores disagree on label",
        translated_message="application.user_profile.errors.profile_integrity_label_mismatch",
        sensitive_tokens=(_PROFILE_UUID, "Renamed Operator", "Aggregate Operator"),
    )


# ── UTC helper migration: validate_utc_aware semantics ─────────────────────


def _aggregate(**overrides: object) -> ProfileAggregate:

    defaults: dict[str, object] = {
        "profile_id": _PROFILE_UUID,
        "label": "Aggregate Operator",
        "created_at": datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC),
        "kdf_params": _kdf_params(),
        "recovery_enrolled": False,
        "manifest_schema_version": 1,
        "record": _record(),
        "status": UserProfileStatus.ACTIVE,
    }
    defaults.update(overrides)
    return ProfileAggregate.model_validate(defaults)


def test_aggregate_rejects_naive_created_at() -> None:
    """A naive created_at must be rejected at the aggregate boundary."""
    with pytest.raises(ValidationError):
        _aggregate(created_at=datetime(2026, 1, 4, 9, 0, 0))


def test_aggregate_rejects_non_utc_created_at() -> None:
    """A timezone-aware but non-UTC created_at must be rejected."""
    plus_one = timezone(timedelta(hours=1))
    with pytest.raises(ValidationError):
        _aggregate(created_at=datetime(2026, 1, 4, 9, 0, 0, tzinfo=plus_one))


def test_aggregate_accepts_utc_created_at() -> None:
    """A UTC-aware created_at is accepted and preserved unchanged."""
    ts = datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC)
    agg = _aggregate(created_at=ts)
    assert agg.created_at == ts
