"""Tests for the user-profile lifecycle and snapshot secure-DB repositories."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider, StorageValidationError
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...core.config import Settings, override_settings
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSnapshotNotFoundError,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    new_profile_snapshot_id,
)
from . import (
    USER_PROFILE_SNAPSHOT_NAMESPACE,
    USER_PROFILE_VALUE_NAMESPACE,
    UserProfileLifecycleRepository,
    UserProfileSnapshotRepository,
    user_profile_snapshot_object_key,
    user_profile_value_object_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
        )
        Base.metadata.create_all(engine)
        try:
            yield SecureObjectRepository(engine=engine)
        finally:
            engine.dispose()


def test_object_key_helpers_reject_blank_inputs() -> None:
    with pytest.raises(ValueError, match="profile_id must not be blank"):
        user_profile_value_object_key("  ")
    with pytest.raises(ValueError, match="profile_id must not be blank"):
        user_profile_snapshot_object_key(" ", "snap-1")
    with pytest.raises(ValueError, match="snapshot_id must not be blank"):
        user_profile_snapshot_object_key("a4f1c2e0-1111-4222-8333-444455556666", "")


def test_object_key_helpers_compose_canonical_keys() -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"
    # The profile-value key is single-segment: a profile bucket holds
    # exactly one live profile-value record, keyed on the immutable UUID.
    assert user_profile_value_object_key(profile_id) == f"user-profile:{profile_id}"
    # The snapshot key keeps the snapshot discriminator: a profile owns
    # many filing snapshots.
    assert (
        user_profile_snapshot_object_key(profile_id, "snap:2026")
        == f"user-profile-snapshot:{profile_id}:snap:2026"
    )


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
    with (
        EphemeralMasterKeyProvider(),
        override_settings(
            aeat_local_storage_root=tmp_path,
            aeat_active_profile=None,
        ),
    ):
        bucket_a = UserProfileLifecycleRepository(bucket_id=profile_a)
        bucket_b = UserProfileLifecycleRepository(bucket_id=profile_b)

        bucket_a.save(profile)

        assert bucket_a.exists(profile_a) is True
        assert bucket_b.exists(profile_a) is False
        assert (tmp_path / "buckets" / profile_a / "db" / "aeat.db").is_file()


def test_default_lifecycle_repository_refuses_explicit_database_url(tmp_path: Path) -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"

    with (
        EphemeralMasterKeyProvider(),
        override_settings(
            aeat_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
            aeat_local_storage_root=tmp_path,
            aeat_active_profile=None,
        ),
        pytest.raises(StorageValidationError, match="not attached to an active profile bucket"),
    ):
        UserProfileLifecycleRepository(bucket_id=profile_id)

    assert not (tmp_path / "explicit.db").exists()
    assert not (tmp_path / "buckets" / profile_id / "db" / "aeat.db").exists()


def test_default_lifecycle_repository_requires_ready_runtime(tmp_path: Path) -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile=None),
        pytest.raises(StorageValidationError, match="storage runtime is not ready"),
    ):
        UserProfileLifecycleRepository(bucket_id=profile_id)


def test_lifecycle_load_missing_raises_profile_not_found(secure_objects: SecureObjectRepository) -> None:
    repo = UserProfileLifecycleRepository(bucket_id="bucket-a", objects=secure_objects)
    with pytest.raises(ProfileNotFoundError, match="operator"):
        repo.load("operator")


def test_snapshot_round_trip_carries_canonical_hash(secure_objects: SecureObjectRepository) -> None:
    profile = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    snapshot_id = new_profile_snapshot_id("operator")
    snapshot = UserProfileSnapshot.from_profile(profile, snapshot_id=snapshot_id)
    repo = UserProfileSnapshotRepository(bucket_id="bucket-a", objects=secure_objects)

    repo.save(snapshot)
    assert repo.exists(snapshot_id)
    reloaded = repo.load(snapshot_id)
    assert reloaded.canonical_hash == snapshot.canonical_hash
    assert reloaded.facts == snapshot.facts


def test_snapshot_load_missing_raises_snapshot_not_found(secure_objects: SecureObjectRepository) -> None:
    repo = UserProfileSnapshotRepository(bucket_id="bucket-a", objects=secure_objects)
    with pytest.raises(ProfileSnapshotNotFoundError, match="missing"):
        repo.load("missing")


def test_lifecycle_namespace_is_stable() -> None:
    assert USER_PROFILE_VALUE_NAMESPACE == "aeat.application.user_profile.value"
    assert USER_PROFILE_SNAPSHOT_NAMESPACE == "aeat.application.user_profile.snapshot"
