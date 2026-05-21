"""Unit tests for :class:`ProfileAggregate` and :func:`verify_profile_integrity`.

The aggregate is the whole-profile in-memory object; its
model-validator rejects an aggregate whose projections disagree on
identity. :func:`verify_profile_integrity` is the read-time gate the
repository runs before the aggregate is even constructed. Both are the
structural defence against the ghost-profile / ``missing_profile_record``
defect class.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ...adapters.persistence.storage.bucket._manifest import (
    BucketLifecycleStatus,
    ManifestKdfParams,
)
from ...domain.user_profile import UserProfileRecord, UserProfileStatus
from ._aggregate import ProfileAggregate
from ._integrity import ProfileIntegrityError, verify_profile_integrity

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

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


def test_aggregate_rejects_record_profile_id_mismatch() -> None:
    """An aggregate whose record carries a different UUID is rejected."""

    with pytest.raises(ValidationError):
        ProfileAggregate(
            profile_id=_PROFILE_UUID,
            label="Aggregate Operator",
            created_at=datetime(2026, 1, 4, 9, 0, 0, tzinfo=UTC),
            kdf_params=_kdf_params(),
            recovery_enrolled=False,
            manifest_schema_version=1,
            record=_record("00000000-0000-4000-8000-000000000000"),
            status=UserProfileStatus.ACTIVE,
        )


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
    with pytest.raises(ValidationError, match="torn rename"):
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


def test_aggregate_rejects_status_mismatch() -> None:
    """An aggregate whose status disagrees with the record is rejected."""

    with pytest.raises(ValidationError):
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


def test_verify_integrity_passes_when_every_store_agrees() -> None:
    """No exception when directory, manifest, and record agree."""

    verify_profile_integrity(
        profile_id=_PROFILE_UUID,
        directory_name=_PROFILE_UUID,
        manifest_bucket_id=_PROFILE_UUID,
        record_profile_id=_PROFILE_UUID,
        manifest_status="active",
        record_status="active",
    )


def test_verify_integrity_raises_on_manifest_drift() -> None:
    """A manifest bucket_id that disagrees raises ProfileIntegrityError."""

    with pytest.raises(ProfileIntegrityError, match="manifest bucket_id"):
        verify_profile_integrity(
            profile_id=_PROFILE_UUID,
            directory_name=_PROFILE_UUID,
            manifest_bucket_id="00000000-0000-4000-8000-000000000000",
            record_profile_id=_PROFILE_UUID,
            manifest_status="active",
            record_status="active",
        )


def test_verify_integrity_raises_on_record_drift() -> None:
    """A record profile_id that disagrees raises ProfileIntegrityError."""

    with pytest.raises(ProfileIntegrityError, match="secure-record profile_id"):
        verify_profile_integrity(
            profile_id=_PROFILE_UUID,
            directory_name=_PROFILE_UUID,
            manifest_bucket_id=_PROFILE_UUID,
            record_profile_id="00000000-0000-4000-8000-000000000000",
            manifest_status="active",
            record_status="active",
        )


def test_lifecycle_status_enums_stay_value_synced() -> None:
    """``BucketLifecycleStatus`` and ``UserProfileStatus`` carry the same values.

    The plaintext manifest mirrors the encrypted record's lifecycle
    status; ``_manifest_status_for`` maps the two enums by string
    value, and ``verify_profile_integrity`` compares them by value. A
    state added to one enum but not the other would silently break
    that mapping — this guard fails the moment the two diverge.
    """

    assert {member.value for member in UserProfileStatus} == {
        member.value for member in BucketLifecycleStatus
    }


def test_verify_integrity_raises_on_lifecycle_status_drift() -> None:
    """A manifest status that disagrees with the record status raises.

    A manifest saying ``active`` over a tombstoned record is the drift
    state that re-opens the tombstone leak; the integrity gate must
    surface it rather than serve the profile.
    """

    with pytest.raises(ProfileIntegrityError, match="cross-store lifecycle drift"):
        verify_profile_integrity(
            profile_id=_PROFILE_UUID,
            directory_name=_PROFILE_UUID,
            manifest_bucket_id=_PROFILE_UUID,
            record_profile_id=_PROFILE_UUID,
            manifest_status="active",
            record_status="tombstoned",
        )
