"""Tests for the user-profile lifecycle and snapshot secure-DB repositories."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage import (
    USER_PROFILE_SNAPSHOT_NAMESPACE as USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE,
)
from ....adapters.persistence.storage import (
    USER_PROFILE_VALUE_NAMESPACE as USER_PROFILE_VALUE_STORAGE_NAMESPACE,
)
from ....adapters.persistence.storage import (
    Envelope,
    SensitivityClass,
    StorageValidationError,
)
from ....adapters.persistence.storage.bucket._errors import BucketValidationError
from ....adapters.persistence.storage.errors import ClassificationError, EnvelopeVersionError
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import override_settings
from ....core.i18n import tr
from ....core.time import now
from ....domain.user_profile import (
    ProfileNotFoundError,
    ProfileSnapshotNotFoundError,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    new_profile_snapshot_id,
)
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from .. import (
    USER_PROFILE_SNAPSHOT_NAMESPACE,
    USER_PROFILE_VALUE_NAMESPACE,
    UserProfileLifecycleRepository,
    UserProfileSnapshotRepository,
    user_profile_snapshot_object_key,
    user_profile_value_object_key,
)
from .._orchestration import profile_create_storage_span

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="user-profile-repository-test",
    ) as profile:
        yield profile.repository


def test_object_key_helpers_reject_blank_inputs() -> None:
    with pytest.raises(BucketValidationError, match="profile_id must not be blank"):
        user_profile_value_object_key("  ")
    with pytest.raises(BucketValidationError, match="profile_id must not be blank"):
        user_profile_snapshot_object_key(" ", "snap-1")
    with pytest.raises(BucketValidationError, match="snapshot_id must not be blank"):
        user_profile_snapshot_object_key("a4f1c2e0-1111-4222-8333-444455556666", "")


def test_object_key_helpers_compose_canonical_keys() -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"
    # The profile-value key is single-segment: a profile bucket holds
    # exactly one live profile-value record, keyed on the immutable UUID.
    assert user_profile_value_object_key(profile_id) == f"user-profile:{profile_id}"
    # The snapshot key keeps the snapshot discriminator: a profile owns
    # many filing snapshots.
    assert user_profile_snapshot_object_key(profile_id, "snap:2026") == f"user-profile-snapshot:{profile_id}:snap:2026"


def test_lifecycle_round_trip_carries_record(secure_objects: SecureObjectRepository) -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"
    profile = UserProfileRecord(
        profile_id=profile_id,
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    repository = UserProfileLifecycleRepository(bucket_id=profile_id, objects=secure_objects)

    assert repository.exists(profile_id) is False
    repository.save(profile)
    assert repository.exists(profile_id) is True

    reloaded = repository.load(profile_id)
    assert reloaded.profile_id == profile_id
    assert reloaded.facts == profile.facts


def test_default_lifecycle_repository_binds_named_bucket_database(tmp_path: Path) -> None:
    profile_a = "a4f1c2e0-1111-4222-8333-444455556666"
    profile_b = "b5e2d3f1-2222-4333-8444-555566667777"
    profile = UserProfileRecord(
        profile_id=profile_a,
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        with profile_create_storage_span(profile_a):
            bucket_a = UserProfileLifecycleRepository(bucket_id=profile_a)
            bucket_a.save(profile)
            assert bucket_a.exists(profile_a) is True

        with profile_create_storage_span(profile_b):
            bucket_b = UserProfileLifecycleRepository(bucket_id=profile_b)
            assert bucket_b.exists(profile_a) is False

        assert (storage_root / "buckets" / profile_a / "db" / "aeat.db").is_file()


def test_default_lifecycle_repository_refuses_explicit_database_url(tmp_path: Path) -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"

    with (
        isolated_profile_storage_root(tmp_path=tmp_path) as storage_root,
        override_settings(
            aeat_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
            aeat_local_storage_root=storage_root,
            aeat_active_profile=None,
        ),
        pytest.raises(StorageValidationError, match="not attached to an active profile bucket"),
    ):
        UserProfileLifecycleRepository(bucket_id=profile_id)

    assert not (tmp_path / "explicit.db").exists()
    assert not (storage_root / "buckets" / profile_id / "db" / "aeat.db").exists()


def test_default_lifecycle_repository_requires_ready_runtime(tmp_path: Path) -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None),
        pytest.raises(StorageValidationError, match="storage runtime is not ready"),
    ):
        UserProfileLifecycleRepository(bucket_id=profile_id)


def test_lifecycle_load_missing_raises_profile_not_found(secure_objects: SecureObjectRepository) -> None:
    repo = UserProfileLifecycleRepository(bucket_id="bucket-a", objects=secure_objects)
    with pytest.raises(ProfileNotFoundError) as excinfo:
        repo.load("11111111-1111-4111-8111-111111111111")
    assert str(excinfo.value) == "profile record not found in secure storage"
    assert excinfo.value.translated_message == "application.user_profile.errors.repository_profile_record_missing"
    assert tr(excinfo.value.translated_message, locale="en") != excinfo.value.translated_message
    assert excinfo.value.context == {"profile_id": "11111111-1111-4111-8111-111111111111", "bucket_id": "bucket-a"}
    assert "11111111-1111-4111-8111-111111111111" not in str(excinfo.value)


def test_lifecycle_load_rejects_inner_classification_without_identifier_leak(
    secure_objects: SecureObjectRepository,
) -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"
    profile = UserProfileRecord(
        profile_id=profile_id,
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    envelope = Envelope[UserProfileRecord](
        schema_version=USER_PROFILE_VALUE_STORAGE_NAMESPACE.schema_version,
        written_at=now(),
        classification=SensitivityClass.FINANCIAL,
        payload=profile,
    )
    secure_objects.save(
        namespace=USER_PROFILE_VALUE_NAMESPACE,
        object_key=user_profile_value_object_key(profile_id),
        classification=USER_PROFILE_VALUE_STORAGE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_VALUE_STORAGE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(ClassificationError) as excinfo:
        UserProfileLifecycleRepository(bucket_id="bucket-a", objects=secure_objects).load(profile_id)

    assert str(excinfo.value) == "profile record classification is incompatible with this repository"
    assert (
        excinfo.value.translated_message
        == "application.user_profile.errors.repository_profile_record_classification_mismatch"
    )
    assert excinfo.value.context == {
        "profile_id": profile_id,
        "classification": SensitivityClass.FINANCIAL.value,
        "expected": USER_PROFILE_VALUE_STORAGE_NAMESPACE.sensitivity.value,
    }
    assert profile_id not in str(excinfo.value)


def test_lifecycle_load_rejects_inner_version_without_identifier_leak(
    secure_objects: SecureObjectRepository,
) -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"
    profile = UserProfileRecord(
        profile_id=profile_id,
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    envelope = Envelope[UserProfileRecord](
        schema_version=USER_PROFILE_VALUE_STORAGE_NAMESPACE.schema_version + 1,
        written_at=now(),
        classification=USER_PROFILE_VALUE_STORAGE_NAMESPACE.sensitivity,
        payload=profile,
    )
    secure_objects.save(
        namespace=USER_PROFILE_VALUE_NAMESPACE,
        object_key=user_profile_value_object_key(profile_id),
        classification=USER_PROFILE_VALUE_STORAGE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_VALUE_STORAGE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(EnvelopeVersionError) as excinfo:
        UserProfileLifecycleRepository(bucket_id="bucket-a", objects=secure_objects).load(profile_id)

    assert str(excinfo.value) == "profile record schema version is not supported"
    assert (
        excinfo.value.translated_message
        == "application.user_profile.errors.repository_profile_record_version_unsupported"
    )
    assert excinfo.value.context == {
        "profile_id": profile_id,
        "schema_version": USER_PROFILE_VALUE_STORAGE_NAMESPACE.schema_version + 1,
        "max_supported_version": USER_PROFILE_VALUE_STORAGE_NAMESPACE.schema_version,
    }
    assert profile_id not in str(excinfo.value)


def test_snapshot_round_trip_carries_canonical_hash(secure_objects: SecureObjectRepository) -> None:
    profile = UserProfileRecord(
        profile_id="11111111-1111-4111-8111-111111111111",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    snapshot_id = new_profile_snapshot_id("11111111-1111-4111-8111-111111111111")
    snapshot = UserProfileSnapshot.from_profile(profile, snapshot_id=snapshot_id)
    repo = UserProfileSnapshotRepository(bucket_id="bucket-a", objects=secure_objects)

    repo.save(snapshot)
    assert repo.exists(snapshot_id)
    reloaded = repo.load(snapshot_id)
    assert reloaded.canonical_hash == snapshot.canonical_hash
    assert reloaded.facts == snapshot.facts


def test_snapshot_load_missing_raises_snapshot_not_found(secure_objects: SecureObjectRepository) -> None:
    repo = UserProfileSnapshotRepository(bucket_id="bucket-a", objects=secure_objects)
    with pytest.raises(ProfileSnapshotNotFoundError) as excinfo:
        repo.load("missing")
    assert str(excinfo.value) == "profile snapshot not found in secure storage"
    assert excinfo.value.translated_message == "application.user_profile.errors.repository_profile_snapshot_missing"
    assert tr(excinfo.value.translated_message, locale="en") != excinfo.value.translated_message
    assert excinfo.value.context == {"snapshot_id": "missing", "bucket_id": "bucket-a"}
    assert "missing" not in str(excinfo.value)


def test_snapshot_load_rejects_inner_classification_without_identifier_leak(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = UserProfileRecord(
        profile_id="a4f1c2e0-1111-4222-8333-444455556666",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    snapshot = UserProfileSnapshot.from_profile(profile, snapshot_id=new_profile_snapshot_id(profile.profile_id))
    envelope = Envelope[UserProfileSnapshot](
        schema_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=now(),
        classification=SensitivityClass.FINANCIAL,
        payload=snapshot,
    )
    secure_objects.save(
        namespace=USER_PROFILE_SNAPSHOT_NAMESPACE,
        object_key=user_profile_snapshot_object_key("bucket-a", snapshot.snapshot_id),
        classification=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(ClassificationError) as excinfo:
        UserProfileSnapshotRepository(bucket_id="bucket-a", objects=secure_objects).load(snapshot.snapshot_id)

    assert str(excinfo.value) == "profile snapshot classification is incompatible with this repository"
    assert (
        excinfo.value.translated_message
        == "application.user_profile.errors.repository_profile_snapshot_classification_mismatch"
    )
    assert excinfo.value.context == {
        "snapshot_id": snapshot.snapshot_id,
        "classification": SensitivityClass.FINANCIAL.value,
        "expected": USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity.value,
    }
    assert snapshot.snapshot_id not in str(excinfo.value)


def test_snapshot_load_rejects_inner_version_without_identifier_leak(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = UserProfileRecord(
        profile_id="a4f1c2e0-1111-4222-8333-444455556666",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    snapshot = UserProfileSnapshot.from_profile(profile, snapshot_id=new_profile_snapshot_id(profile.profile_id))
    envelope = Envelope[UserProfileSnapshot](
        schema_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version + 1,
        written_at=now(),
        classification=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity,
        payload=snapshot,
    )
    secure_objects.save(
        namespace=USER_PROFILE_SNAPSHOT_NAMESPACE,
        object_key=user_profile_snapshot_object_key("bucket-a", snapshot.snapshot_id),
        classification=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(EnvelopeVersionError) as excinfo:
        UserProfileSnapshotRepository(bucket_id="bucket-a", objects=secure_objects).load(snapshot.snapshot_id)

    assert str(excinfo.value) == "profile snapshot schema version is not supported"
    assert (
        excinfo.value.translated_message
        == "application.user_profile.errors.repository_profile_snapshot_version_unsupported"
    )
    assert excinfo.value.context == {
        "snapshot_id": snapshot.snapshot_id,
        "schema_version": USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version + 1,
        "max_supported_version": USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
    }
    assert snapshot.snapshot_id not in str(excinfo.value)


def test_lifecycle_namespace_uses_storage_registry() -> None:
    assert USER_PROFILE_VALUE_STORAGE_NAMESPACE.namespace == USER_PROFILE_VALUE_NAMESPACE
    assert USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace == USER_PROFILE_SNAPSHOT_NAMESPACE
