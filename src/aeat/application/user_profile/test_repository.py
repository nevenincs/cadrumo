"""Tests for the user-profile lifecycle and snapshot secure-DB repositories."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...core.config import Settings
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
    with pytest.raises(ValueError, match="bucket_id must not be blank"):
        user_profile_value_object_key("  ", "operator")
    with pytest.raises(ValueError, match="profile_id must not be blank"):
        user_profile_value_object_key("bucket", "  ")
    with pytest.raises(ValueError, match="bucket_id must not be blank"):
        user_profile_snapshot_object_key(" ", "snap-1")
    with pytest.raises(ValueError, match="snapshot_id must not be blank"):
        user_profile_snapshot_object_key("bucket", "")


def test_object_key_helpers_compose_canonical_keys() -> None:
    assert user_profile_value_object_key("bucket-1", "operator") == "user-profile:bucket-1:operator"
    assert (
        user_profile_snapshot_object_key("bucket-1", "operator:2026.snap")
        == "user-profile-snapshot:bucket-1:operator:2026.snap"
    )


def test_lifecycle_round_trip_isolates_by_bucket(secure_objects: SecureObjectRepository) -> None:
    profile = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    bucket_a = UserProfileLifecycleRepository(bucket_id="bucket-a", objects=secure_objects)
    bucket_b = UserProfileLifecycleRepository(bucket_id="bucket-b", objects=secure_objects)

    bucket_a.save(profile)
    assert bucket_a.exists("operator") is True
    assert bucket_b.exists("operator") is False

    reloaded = bucket_a.load("operator")
    assert reloaded.profile_id == "operator"
    assert reloaded.facts == profile.facts


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
