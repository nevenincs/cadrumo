"""Real capsule-backed profile-record setup for application integration tests.

The application profile record is no longer a bucket-row repository.  Modelo
and auth tests still need to seed a record while exercising a real active
bucket session, so this module composes the production capsule lifecycle and
binds the exact record session around each read or replacement.
"""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Iterable, Iterator
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from ..adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
    list_current_profile_custody_capsule_ids,
)
from ..adapters.persistence.storage.master_key import current_active_bucket_session, session_serves_bucket
from ..application.profile_custody import load_profile_custody_password_material
from ..application.user_profile._capsule_record import ProfileRecordSession
from ..application.user_profile._lifecycle import ProfileCapsuleLifecycle
from ..application.user_profile._profile_record_repository import (
    ProfileRecordRepository,
    bound_profile_record_session,
)
from ..core.paths import effective_storage_root
from ..domain.buckets import BucketEventType
from ..domain.user_profile import UserProfileFact, UserProfileRecord


def _active_bucket_dek(profile_id: UUID) -> bytes:
    active = current_active_bucket_session()
    if not session_serves_bucket(active, str(profile_id)):
        raise RuntimeError("profile-record test setup requires the target's active bucket session")
    return active.dek


@contextmanager
def open_test_profile_session(profile_id: str | UUID) -> Iterator[str]:
    """Open one real bucket session for capsule-backed integration tests.

    The application no longer exposes a create-time or generic storage-span
    helper.  Tests that need to exercise an encrypted bucket still need the
    same production custody boundary, however: resolve the configured master
    key provider, enroll/load the target bucket DEK, and bind the resulting
    :class:`BucketSession` while the operation runs.  This test-owned helper
    composes that current substrate without making production import test
    plumbing or reviving either retired application symbol.

    ``allow_bucket_dek_enrollment`` is intentionally enabled because most
    callers use this context while building a synthetic current capsule.  A
    later read against that capsule still opens the exact durable DEK written
    by the first call; no key or repository is faked.

    The record authority is retired on both edges because this helper owns
    the custody span the authority is bound to: retiring on entry is exactly
    what a real profile switch does, and retiring on exit zeroises the DEK
    this span unlocked instead of leaving it latched past the session that
    justified it.  Reachability of a second profile does not depend on either
    edge -- ``require_profile_record_session`` re-derives whenever the latched
    authority does not serve the requested identity.
    """
    identity = str(UUID(str(profile_id)))
    from ..adapters.persistence.storage.errors import (
        MasterKeyMaterialMissingError,
        SecretAlreadyExistsError,
    )
    from ..adapters.persistence.storage.master_key import (
        activate_master_key_provider,
        get_master_key_provider,
    )
    from ..application.user_profile._profile_record_repository import close_active_profile_record_session
    from ..core.config import override_settings

    provider = get_master_key_provider()
    try:
        provider.get_master_key()
    except MasterKeyMaterialMissingError:
        with suppress(SecretAlreadyExistsError):
            provider.provision_master_key()
    close_active_profile_record_session()
    try:
        with (
            override_settings(cadrumo_active_profile=identity),
            activate_master_key_provider(
                provider,
                fallback_bucket_id=identity,
                allow_bucket_dek_enrollment=True,
            ),
        ):
            yield identity
    finally:
        close_active_profile_record_session()


def _new_test_envelope(profile_id: UUID) -> ProfileCustodyEnvelope:
    seed = sha256(f"profile-record-test:{profile_id}".encode("ascii")).digest()
    second = sha256(seed).digest()
    return ProfileCustodyEnvelope.create(
        profile_id=profile_id,
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
            tag_b64=b64encode(second[:16]).decode("ascii"),
        ),
    )


def _record_session(profile_id: UUID, *, root: Path) -> ProfileRecordSession:
    material = load_profile_custody_password_material(profile_id, root=root)
    return ProfileRecordSession.from_envelope(
        envelope=material.envelope,
        dek=_active_bucket_dek(profile_id),
    )


def _rebuild_record(record: UserProfileRecord, **updates: object) -> UserProfileRecord:
    payload = record.model_dump()
    payload.pop("content_digest", None)
    payload.update(updates)
    return UserProfileRecord.model_validate(payload)


@contextmanager
def bound_test_profile_record(
    profile_id: str | UUID,
    *,
    root: Path | None = None,
) -> Iterator[ProfileRecordRepository]:
    """Yield the current repository while its real record session is bound."""
    identity = UUID(str(profile_id))
    storage_root = effective_storage_root(root)
    session = _record_session(identity, root=storage_root)
    try:
        with bound_profile_record_session(session):
            yield ProfileRecordRepository.for_current_session(identity, root=storage_root)
    finally:
        session.close()


def load_test_profile_record(
    profile_id: str | UUID,
    *,
    root: Path | None = None,
) -> UserProfileRecord:
    """Read one current record through a bound real capsule session."""
    identity = UUID(str(profile_id))
    with bound_test_profile_record(identity, root=root) as repository:
        return repository.load(identity)


def replace_test_profile_record(
    record: UserProfileRecord,
    *,
    root: Path | None = None,
    event_type: str = BucketEventType.PROFILE_VALUES_UPDATED.value,
) -> UserProfileRecord:
    """CAS-replace a seeded record through the production capsule writer."""
    identity = UUID(str(record.profile_id))
    storage_root = effective_storage_root(root)
    with bound_test_profile_record(identity, root=storage_root) as repository:
        current = repository.load(identity)
        replacement = _rebuild_record(
            record,
            record_revision=current.record_revision + 1,
            previous_record_digest=current.content_digest,
            updated_at=datetime.now(UTC),
        )
        repository.apply_fact_changes(
            identity,
            facts=replacement.facts,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            event_type=event_type,
            event_payload={},
            now=replacement.updated_at,
        )
        return repository.load(identity)


def upsert_test_profile_facts(
    profile_id: str | UUID,
    facts: Iterable[UserProfileFact],
    *,
    root: Path | None = None,
) -> UserProfileRecord:
    """Merge facts onto a seeded record through the production capsule writer.

    The record writer takes the complete next fact sequence rather than a
    patch, so the merge is composed here: same-path facts replace in place and
    new ones append in declaration order.  Tests that used to layer a handful
    of answers onto a minimal profile get the same effect without any
    application-side upsert command, and every write still goes through the
    real revision compare-and-swap.
    """
    identity = UUID(str(profile_id))
    storage_root = effective_storage_root(root)
    with bound_test_profile_record(identity, root=storage_root) as repository:
        current = repository.load(identity)
        merged: dict[str, UserProfileFact] = {fact.path: fact for fact in current.facts}
        for fact in facts:
            merged[fact.path] = fact
        repository.apply_fact_changes(
            identity,
            facts=tuple(merged.values()),
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            event_type=BucketEventType.PROFILE_VALUES_UPDATED.value,
            event_payload={},
            now=datetime.now(UTC),
        )
        return repository.load(identity)


def set_active_test_profile_facts(
    facts: Iterable[UserProfileFact],
    *,
    root: Path | None = None,
) -> UserProfileRecord:
    """Merge facts onto the ACTIVE profile's seeded record.

    The successor to the retired application-side plural fact command, for the
    many suites that seed a minimal profile and then layer a handful of
    answers onto whichever profile the test made active.  Selection is read
    through the production precedence chain rather than passed in, so a test
    that forgot to select a profile fails here instead of silently writing to
    a different capsule.
    """
    from ..core import resolve_active_bucket_id

    active = resolve_active_bucket_id()
    if active is None:
        raise RuntimeError("no active profile is selected; seed and select one before setting facts")
    return upsert_test_profile_facts(active, facts, root=root)


def seed_test_profile_record(
    record: UserProfileRecord,
    *,
    root: Path | None = None,
    label: str = "Test profile",
) -> UserProfileRecord:
    """Create or replace one record in a genuine committed profile capsule."""
    identity = UUID(str(record.profile_id))
    storage_root = effective_storage_root(root)
    dek = _active_bucket_dek(identity)
    if identity not in list_current_profile_custody_capsule_ids(root=storage_root):
        envelope = _new_test_envelope(identity)
        session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
        initial = _rebuild_record(
            record,
            profile_id=str(identity),
            record_revision=1,
            previous_record_digest=None,
        )
        try:
            ProfileCapsuleLifecycle(root=storage_root).create(
                label=label,
                profile_id=identity,
                password_envelope=envelope,
                sentinel=create_profile_custody_sentinel(envelope=envelope, dek=dek),
                data_files={},
                initial_record=initial,
                record_session=session,
            )
        finally:
            session.close()
        return initial
    return replace_test_profile_record(
        record,
        root=storage_root,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED.value,
    )


__all__ = [
    "bound_test_profile_record",
    "load_test_profile_record",
    "open_test_profile_session",
    "replace_test_profile_record",
    "seed_test_profile_record",
    "set_active_test_profile_facts",
    "upsert_test_profile_facts",
]
