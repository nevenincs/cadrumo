"""Real capsule-backed profile-record setup for application integration tests.

The application profile record is no longer a bucket-row repository.  Modelo
and auth tests still need to seed a record while exercising a real active
bucket session, so this module composes the production capsule lifecycle and
binds the exact record session around each read or replacement.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from ..adapters.persistence.storage import custody
from ..adapters.persistence.storage.custody import (
    create_profile_custody_sentinel,
    list_current_profile_custody_capsule_ids,
)
from ..adapters.persistence.storage.master_key import current_active_bucket_session, session_serves_bucket
from ..adapters.persistence.storage.tests.profile_capsule_runtime import (
    derive_test_bucket_key,
    new_test_profile_custody_envelope,
    test_profile_recovery_envelope,
)
from ..application.user_profile.lifecycle import ProfileCapsuleLifecycle
from ..application.user_profile.custody_ports import ProfileCustodyRecoveryEnvelopePort
from ..application.user_profile.profile_record_repository import ProfileRecordRepository, bound_profile_record_session, close_active_profile_record_session
from ..application.user_profile.capsule_record import ProfileRecordSession
from ..core.identity import canonical_profile_bucket_id
from ..core.paths import effective_storage_root
from ..domain.buckets import BucketEventType
from ..domain.user_profile.errors import ProfileSchemaValidationError
from ..domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord


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
    same production custody boundary, however: obtain the target bucket's data
    key and bind the resulting :class:`BucketSession` while the operation runs.
    This test-owned helper composes that current substrate without making
    production import test plumbing or reviving any retired application symbol.

    Two ways in, and the first is what makes a login-first test work.  When a
    live session already serves this bucket -- because the test authenticated
    through the real login door -- that session IS the custody span and is
    reused untouched, so the helper never substitutes a key for one the
    operator's passphrase unlocked.

    Otherwise the bucket has no custody to unlock (the common case: callers
    build a synthetic capsule inside this span), and the helper derives the
    bucket's data key deterministically from its immutable identity.  Nothing
    is faked: it is a real 32-byte key opening a real session over real
    encrypted records.  Determinism is what the contract needs -- a later read
    inside the same test opens the exact key the first call bound -- and it
    replaces a persisted keystore artefact that no production path writes.

    The record authority is retired on both edges because this helper owns
    the custody span the authority is bound to: retiring on entry is exactly
    what a real profile switch does, and retiring on exit zeroises the DEK
    this span unlocked instead of leaving it latched past the session that
    justified it.  Reachability of a second profile does not depend on either
    edge -- ``require_profile_record_session`` re-derives whenever the latched
    authority does not serve the requested identity.
    """
    identity = str(UUID(str(profile_id)))
    from ..adapters.persistence.storage.master_key import (
        BucketSession,
        activate_session,
    )
    from ..core.config import override_settings

    live = current_active_bucket_session()
    if session_serves_bucket(live, identity):
        with override_settings(cadrumo_active_profile=identity):
            yield identity
        return

    close_active_profile_record_session()
    try:
        with override_settings(cadrumo_active_profile=identity):
            session = BucketSession.open(
                bucket_id=identity,
                kek=derive_test_bucket_key(identity, purpose="kek"),
                dek=derive_test_bucket_key(identity, purpose="dek"),
                idle_minutes=15,
                opened_at=datetime.now(UTC),
                storage_root=effective_storage_root(),
            )
            with activate_session(session):
                yield identity
    finally:
        close_active_profile_record_session()


def mint_test_profile_recovery_envelope(
    profile_id: UUID,
    *,
    dek: bytes,
    dek_epoch: str,
) -> ProfileCustodyRecoveryEnvelopePort:
    """Mint a creation wrapper while immediately wiping the fixture mnemonic."""
    with test_profile_recovery_envelope(profile_id, dek=dek, dek_epoch=dek_epoch) as envelope:
        return envelope


def _record_session(profile_id: UUID, *, root: Path) -> ProfileRecordSession:
    material = custody.load_committed_profile_password_material(profile_id, root=root)
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
    identity = UUID(canonical_profile_bucket_id(profile_id))
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
    identity = UUID(canonical_profile_bucket_id(profile_id))
    with bound_test_profile_record(identity, root=root) as repository:
        return repository.load(identity)


def replace_test_profile_record(
    record: UserProfileRecord,
    *,
    root: Path | None = None,
    event_type: BucketEventType = BucketEventType.PROFILE_VALUES_UPDATED,
) -> UserProfileRecord:
    """CAS-replace a seeded record's facts AND its setup state through the production doors.

    The fact writer takes facts and nothing else, so replacing a record through
    it alone silently dropped every other field the caller declared. A test
    seeding ``setup_state = COMPLETE`` got its sixteen facts and an INCOMPLETE
    record back, and the modelo readiness gate then refused the "ready" profile
    with ``profile_readiness_setup_incomplete`` -- reporting no missing field,
    because none was missing.

    The promotion goes through :meth:`ProfileRecordRepository.complete_setup`
    rather than writing the state directly, because that door JUDGES: COMPLETE
    is the claim that nothing schema-required is absent, and a fixture whose
    facts do not support the claim must be refused here rather than seeded into
    a state no production path could produce.
    """
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
        if record.setup_state is ProfileSetupState.COMPLETE:
            applied = repository.load(identity)
            if applied.setup_state is not ProfileSetupState.COMPLETE:
                # The caller's facts cannot support the claim, and NO production
                # path can mint that record either -- COMPLETE asserts that
                # nothing schema-required is absent. Leaving the record as
                # applied is the honest answer rather than a silent one: many
                # fixtures seed a deliberately minimal fact set for the
                # behaviour under test and never read the state, and a fixture
                # that DOES depend on it meets the readiness gate's
                # missing-field refusal, which names what to add. The case this
                # promotion exists for is the opposite one -- a schema-complete
                # fact set whose state was dropped, where that gate could only
                # say "incomplete" and enumerate nothing.
                with contextlib.suppress(ProfileSchemaValidationError):
                    repository.complete_setup(
                        identity,
                        expected_revision=applied.record_revision,
                        expected_content_digest=applied.content_digest,
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
    identity = UUID(canonical_profile_bucket_id(profile_id))
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
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
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
    from ..core.bucket_pointer import resolve_active_bucket_id

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
        envelope = new_test_profile_custody_envelope(identity)
        session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
        initial = _rebuild_record(
            record,
            profile_id=str(identity),
            record_revision=1,
            previous_record_digest=None,
        )
        try:
            with test_profile_recovery_envelope(
                identity,
                dek=dek,
                dek_epoch=envelope.dek_epoch,
            ) as recovery_envelope:
                ProfileCapsuleLifecycle(root=storage_root).create(
                    label=label,
                    profile_id=identity,
                    password_envelope=envelope,
                    sentinel=create_profile_custody_sentinel(envelope=envelope, dek=dek),
                    data_files={},
                    initial_record=initial,
                    record_session=session,
                    recovery_envelope=recovery_envelope,
                )
        finally:
            session.close()
        return initial
    return replace_test_profile_record(
        record,
        root=storage_root,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
    )


def forge_colliding_capsule_label(*, profile_id: UUID, label: str, root: Path | None = None) -> None:
    """Write one committed capsule's label to a value every writer would refuse.

    NO SUPPORTED PATH PRODUCES THIS STATE. Every label writer -- capsule
    creation and label rename alike -- routes through the custody service's
    duplicate check under the custody-root lock, which compares casefolded, so
    two committed capsules can never carry casefold-equal labels by any
    operator action. Nothing here suggests otherwise: this manufactures on-disk
    corruption on purpose, so that the read-side backstops which refuse an
    ambiguous label can be exercised at all. A backstop against a state every
    writer prevents is untestable without forging it.

    The sequence mirrors the custody service's own rename transaction -- advance
    the durable lineage head, replace the committed label record against its
    expected digest, then re-verify the head -- omitting only the duplicate
    refusal. Keeping the same order is what makes the forged state coherent
    rather than merely broken: the label record and its verification head still
    agree, which is exactly the state a reader must disambiguate.

    The service takes the custody-root transaction lock around this sequence.
    This does not, because a test forging a state has no concurrent writer to
    exclude, and the lock is not on the custody package's public facade.
    """
    from ..adapters.persistence.storage.custody import (
        PROFILE_CUSTODY_LABEL_FILENAME,
        ProfileCustodyCapsuleLabel,
        ProfileLabelHeadRepository,
        load_committed_profile_custody_label_record,
        replace_committed_profile_custody_data_file,
    )
    from ..core.config import load_settings
    from ..core.hashing import prefixed_digest

    resolved_root = root if root is not None else load_settings().cadrumo_local_storage_root
    if resolved_root is None:
        raise RuntimeError("forging a capsule label requires a configured local storage root")

    current = load_committed_profile_custody_label_record(profile_id, root=resolved_root)
    heads = ProfileLabelHeadRepository(root=resolved_root)
    current_head = heads.recover_advance(profile_id=profile_id, current_label=current)
    replacement = ProfileCustodyCapsuleLabel.create(
        profile_id=profile_id,
        label=label,
        label_revision=current.label_revision + 1,
        previous_label_digest=current.content_digest,
    )
    heads.begin_advance(
        current_head=current_head,
        current_label=current,
        replacement_label=replacement,
    )
    replace_committed_profile_custody_data_file(
        profile_id,
        PROFILE_CUSTODY_LABEL_FILENAME,
        replacement.canonical_json_bytes(),
        expected_sha256=prefixed_digest(current.canonical_json_bytes()),
        root=resolved_root,
    )
    heads.recover_advance(profile_id=profile_id, current_label=replacement)


__all__ = [
    "bound_test_profile_record",
    "forge_colliding_capsule_label",
    "load_test_profile_record",
    "mint_test_profile_recovery_envelope",
    "open_test_profile_session",
    "replace_test_profile_record",
    "seed_test_profile_record",
    "set_active_test_profile_facts",
    "upsert_test_profile_facts",
]
