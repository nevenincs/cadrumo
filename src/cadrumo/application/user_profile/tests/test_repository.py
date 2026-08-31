"""Tests for current-record and immutable-snapshot profile repositories.

The live ``UserProfileRecord`` is now owned by the committed capsule.  Its
application repository is intentionally a read-only, authenticated view over
that capsule; snapshots remain the separate bucket-bound secure-object
repository used by filing-time consumers.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from ....adapters.persistence.storage.custody.kdf_supervision import unlock_profile_custody
from ....adapters.persistence.storage.envelope._envelope import Envelope
from ....adapters.persistence.storage.secure_object_namespaces import (
    USER_PROFILE_SNAPSHOT_NAMESPACE as USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE,
)
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.classification.policies import SensitivityClass
from ....core.i18n import tr
from ....core.time.clock import now
from ....domain.user_profile.errors import (
    ProfileBucketMismatchError,
    ProfileNotFoundError,
    ProfileSnapshotClassificationError,
    ProfileSnapshotNotFoundError,
    ProfileSnapshotVersionError,
)
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    new_profile_snapshot_id,
)
from ....tests.profile_capsule import open_test_profile_session, seed_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ..capsule_record import ProfileRecordSession
from ..profile_record_repository import (
    ProfileRecordRepository,
    bound_profile_record_session,
    close_active_profile_record_session,
    require_profile_record_session,
)
from ..registration import register_profile_with_credentials
from ..repository import (
    UserProfileSnapshotRepository,
    user_profile_snapshot_object_key,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_RUNTIME_BUCKET_ID = "8127d068-f112-445b-b90e-ccf5e0139167"
_BUCKET_ID = "eab96552-b170-4499-9436-5f06884dd062"
_FOREIGN_PROFILE_ID = "f7c5a9e3-7b1d-4c2e-8a6f-1234567890ab"
_PROFILE_PASSPHRASE = "repository-current-record-test-passphrase"  # noqa: S105 - synthetic test credential
_FIRST_SWITCH_PROFILE_ID = "3f5f7d94-1a2b-4c3d-8e4f-5a6b7c8d9e01"
_SECOND_SWITCH_PROFILE_ID = "3f5f7d94-1a2b-4c3d-8e4f-5a6b7c8d9e02"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_RUNTIME_BUCKET_ID,
    ) as profile:
        yield profile.repository


@contextmanager
def _registered_record_session(
    tmp_path: Path,
    *,
    facts: tuple[UserProfileFact, ...] = (),
) -> Generator[tuple[Path, str]]:
    """Register a real capsule and bind its unlocked record session."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Current record repository subject",
            passphrase=_PROFILE_PASSPHRASE,
            facts=facts,
        )
        material = load_committed_profile_password_material(UUID(outcome.profile_id), root=storage_root)
        unlocked = unlock_profile_custody(
            material.envelope,
            _PROFILE_PASSPHRASE,
            sentinel=material.sentinel,
        )
        session = ProfileRecordSession.from_envelope(envelope=material.envelope, dek=unlocked.dek)
        try:
            with bound_profile_record_session(session):
                yield storage_root, outcome.profile_id
        finally:
            session.close()


def test_profile_record_repository_reads_the_current_record_through_bound_session(tmp_path: Path) -> None:
    facts = (UserProfileFact(path="identity.tax_id", value="12345678Z"),)
    with _registered_record_session(tmp_path, facts=facts) as (storage_root, profile_id):
        repository = ProfileRecordRepository.for_current_session(profile_id, root=storage_root)

        assert repository.profile_id == UUID(profile_id)
        record = repository.load(profile_id)

    assert record.profile_id == profile_id
    assert record.facts == facts
    assert record.setup_state is ProfileSetupState.INCOMPLETE
    assert set(type(record).model_fields) == {
        "schema_id",
        "schema_version",
        "profile_id",
        "facts",
        "setup_state",
        "record_revision",
        "previous_record_digest",
        "content_digest",
        "created_at",
        "updated_at",
    }


def test_profile_record_repository_requires_an_authenticated_record_session(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        outcome = register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label="Unauthenticated record subject",
            passphrase=_PROFILE_PASSPHRASE,
        )

        with pytest.raises(ProfileNotFoundError, match="authenticated session"):
            ProfileRecordRepository.for_current_session(outcome.profile_id, root=storage_root)


def test_profile_record_repository_refuses_a_foreign_profile_id(tmp_path: Path) -> None:
    with _registered_record_session(tmp_path) as (storage_root, profile_id):
        repository = ProfileRecordRepository.for_current_session(profile_id, root=storage_root)

        with pytest.raises(ProfileNotFoundError, match="does not serve"):
            repository.load(_FOREIGN_PROFILE_ID)


def test_profile_record_repository_rejects_a_non_uuid_identity() -> None:
    with pytest.raises(ProfileNotFoundError, match="canonical UUID"):
        ProfileRecordRepository.for_current_session(" ")


def test_record_authority_re_derives_for_a_second_profile_in_one_process(tmp_path: Path) -> None:
    """A second profile's record stays readable after an in-process switch.

    The ambient-provider fact readers bind the target's own custody session
    and then ask for its record authority.  A process that already read the
    first profile carries that profile's latched authority, so the second
    profile is reachable only when the authority is re-derived from the
    custody session that is actually live.
    """
    first_facts = (UserProfileFact(path="identity.tax_id", value="12345678Z"),)
    second_facts = (UserProfileFact(path="identity.tax_id", value="87654321X"),)
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        for identity, facts, label in (
            (_FIRST_SWITCH_PROFILE_ID, first_facts, "Switch first"),
            (_SECOND_SWITCH_PROFILE_ID, second_facts, "Switch second"),
        ):
            with open_test_profile_session(identity):
                seed_test_profile_record(
                    UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=identity, facts=facts),
                    root=storage_root,
                    label=label,
                )

        try:
            with open_test_profile_session(_FIRST_SWITCH_PROFILE_ID):
                first_repository = ProfileRecordRepository.for_current_session(
                    _FIRST_SWITCH_PROFILE_ID,
                    root=storage_root,
                )
                assert first_repository.load(_FIRST_SWITCH_PROFILE_ID).facts == first_facts

            with open_test_profile_session(_SECOND_SWITCH_PROFILE_ID):
                session = require_profile_record_session(_SECOND_SWITCH_PROFILE_ID)
                assert session.profile_id == UUID(_SECOND_SWITCH_PROFILE_ID)
                second_repository = ProfileRecordRepository.for_current_session(
                    _SECOND_SWITCH_PROFILE_ID,
                    root=storage_root,
                )
                assert second_repository.load(_SECOND_SWITCH_PROFILE_ID).facts == second_facts
        finally:
            close_active_profile_record_session()


def test_snapshot_round_trip_carries_canonical_hash(secure_objects: SecureObjectRepository) -> None:
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    snapshot_id = new_profile_snapshot_id(profile.profile_id)
    snapshot = UserProfileSnapshot.from_profile(profile, snapshot_id=snapshot_id)
    repo = UserProfileSnapshotRepository(bucket_id=profile.profile_id, objects=secure_objects)

    repo.save(snapshot)
    assert repo.exists(snapshot_id)
    reloaded = repo.load(snapshot_id)
    assert reloaded.canonical_hash == snapshot.canonical_hash
    assert reloaded.facts == snapshot.facts


def test_snapshot_repository_refuses_a_foreign_profile_snapshot(
    secure_objects: SecureObjectRepository,
) -> None:
    foreign = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_FOREIGN_PROFILE_ID,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    snapshot = UserProfileSnapshot.from_profile(foreign, snapshot_id=new_profile_snapshot_id(foreign.profile_id))
    repository = UserProfileSnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    with pytest.raises(ProfileBucketMismatchError):
        repository.save(snapshot)

    assert repository.exists(snapshot.snapshot_id) is False


def test_snapshot_repository_round_trip_requires_its_bound_profile(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    snapshot = UserProfileSnapshot.from_profile(profile, snapshot_id=new_profile_snapshot_id(profile.profile_id))
    repository = UserProfileSnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)

    repository.save(snapshot)

    reloaded = repository.load(snapshot.snapshot_id)
    assert reloaded == snapshot
    assert reloaded.profile_id == _BUCKET_ID


def test_snapshot_load_missing_raises_snapshot_not_found(secure_objects: SecureObjectRepository) -> None:
    repo = UserProfileSnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    with pytest.raises(ProfileSnapshotNotFoundError) as excinfo:
        repo.load("missing")
    assert str(excinfo.value) == "profile snapshot not found in secure storage"
    assert excinfo.value.translated_message == "application.user_profile.errors.repository_profile_snapshot_missing"
    assert tr(excinfo.value.translated_message, locale="en") != excinfo.value.translated_message
    assert excinfo.value.context == {"snapshot_id": "missing", "bucket_id": _BUCKET_ID}
    assert "missing" not in str(excinfo.value)


def test_snapshot_load_rejects_inner_classification_without_identifier_leak(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="a4f1c2e0-1111-4222-8333-444455556666",
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
        namespace=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace,
        object_key=user_profile_snapshot_object_key(_BUCKET_ID, snapshot.snapshot_id),
        classification=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(ProfileSnapshotClassificationError) as excinfo:
        UserProfileSnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects).load(snapshot.snapshot_id)

    assert str(excinfo.value) == "secure-object namespace classification does not match the repository contract"
    assert excinfo.value.translated_message == "application.user_profile.errors.repository_classification_mismatch"
    assert excinfo.value.context == {
        "namespace": USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace,
        "snapshot_id": snapshot.snapshot_id,
        "classification": SensitivityClass.FINANCIAL.value,
        "expected": USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity.value,
    }
    assert snapshot.snapshot_id not in str(excinfo.value)


def test_snapshot_load_rejects_inner_version_without_identifier_leak(
    secure_objects: SecureObjectRepository,
) -> None:
    profile = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="a4f1c2e0-1111-4222-8333-444455556666",
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
        namespace=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace,
        object_key=user_profile_snapshot_object_key(_BUCKET_ID, snapshot.snapshot_id),
        classification=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )

    with pytest.raises(ProfileSnapshotVersionError) as excinfo:
        UserProfileSnapshotRepository(bucket_id=_BUCKET_ID, objects=secure_objects).load(snapshot.snapshot_id)

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


def test_snapshot_namespace_name_comes_from_the_storage_registry() -> None:
    assert USER_PROFILE_SNAPSHOT_STORAGE_NAMESPACE.namespace == "cadrumo.application.user_profile.snapshot"


def test_snapshot_object_keys_use_the_current_profile_and_snapshot_id() -> None:
    profile_id = "a4f1c2e0-1111-4222-8333-444455556666"
    assert user_profile_snapshot_object_key(profile_id, "snap:2026") == (
        f"user-profile-snapshot:{profile_id}:snap:2026"
    )


def test_record_authority_re_derives_after_its_latched_session_is_retired(tmp_path: Path) -> None:
    """A retired latched authority is replaced, not handed back.

    Retirement zeroises the key in place and leaves the object latched, so the
    identity check alone cannot tell a retired authority from a working one.
    Before liveness was checked the caller got the UUID-matching corpse back
    and the failure surfaced as an integrity error from inside the decrypt,
    blaming the read for a decision made when the session was reused.

    The custody session is still live here, so the correct outcome is a fresh
    derivation and a successful read -- not merely a tidier refusal.
    """
    facts = (UserProfileFact(path="identity.tax_id", value="12345678Z"),)
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        with open_test_profile_session(_FIRST_SWITCH_PROFILE_ID):
            seed_test_profile_record(
                UserProfileRecord(
                    setup_state=ProfileSetupState.COMPLETE, profile_id=_FIRST_SWITCH_PROFILE_ID, facts=facts
                ),
                root=storage_root,
                label="Retired authority subject",
            )

        try:
            with open_test_profile_session(_FIRST_SWITCH_PROFILE_ID):
                latched = require_profile_record_session(_FIRST_SWITCH_PROFILE_ID)
                assert not latched.closed

                latched.close()
                assert latched.closed, "the subject of this test is a session retired in place"

                replacement = require_profile_record_session(_FIRST_SWITCH_PROFILE_ID)
                assert replacement is not latched, "a retired authority must not be handed back"
                assert not replacement.closed
                assert replacement.profile_id == UUID(_FIRST_SWITCH_PROFILE_ID)

                repository = ProfileRecordRepository.for_current_session(
                    _FIRST_SWITCH_PROFILE_ID,
                    root=storage_root,
                )
                assert repository.load(_FIRST_SWITCH_PROFILE_ID).facts == facts
        finally:
            close_active_profile_record_session()


def test_a_live_latched_authority_is_reused_rather_than_re_derived(tmp_path: Path) -> None:
    """Liveness must gate reuse without abolishing it.

    A guard that re-derived on every call would satisfy the retirement test
    above while quietly discarding the latch, so this pins the other side: a
    live authority is returned as the same object.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        with open_test_profile_session(_FIRST_SWITCH_PROFILE_ID):
            seed_test_profile_record(
                UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_FIRST_SWITCH_PROFILE_ID),
                root=storage_root,
                label="Live authority subject",
            )

        try:
            with open_test_profile_session(_FIRST_SWITCH_PROFILE_ID):
                first = require_profile_record_session(_FIRST_SWITCH_PROFILE_ID)
                assert require_profile_record_session(_FIRST_SWITCH_PROFILE_ID) is first
        finally:
            close_active_profile_record_session()
