"""Concrete profile-capsule runtime composition for persistence-backed tests.

All helpers in this module exercise the encrypted persistence boundary.  They
therefore belong with the storage adapter test support rather than the shared
``cadrumo.tests`` namespace; application tests that need an inward-only value
can use the modelo fixture-value module directly.
"""

from __future__ import annotations

import contextlib
from base64 import b64encode
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from .....application.modelo.tests.profile_fixture_values import MODELO_READY_PROFILE_FACTS
from .....application.user_profile.capsule_record import ProfileRecordSession
from .....application.user_profile.custody_ports import ProfileCustodyRecoveryEnvelopePort
from .....application.user_profile.lifecycle import ProfileCapsuleLifecycle
from .....application.user_profile.profile_record_repository import (
    ProfileRecordRepository,
    bound_profile_record_session,
    close_active_profile_record_session,
)
from .....application.user_profile.recovery_custody import mint_profile_creation_recovery
from .....core.bucket_pointer import resolve_active_bucket_id
from .....core.config import override_settings
from .....core.identity.profile import canonical_profile_bucket_id
from .....core.paths import effective_storage_root
from .....domain.buckets.event import BucketEventType
from .....domain.calculations.registry.authority import bundled_authority
from .....domain.user_profile.errors import ProfileSchemaValidationError
from .....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ..bucket.directory_layout import BucketPaths, bucket_paths
from ..custody.capsule import list_current_profile_custody_capsule_ids, load_committed_profile_password_material
from ..custody.records import ProfileCustodyEnvelope, ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from ..custody.sentinel import create_profile_custody_sentinel
from ..master_key.active_session import activate_session, current_active_bucket_session, session_serves_bucket
from ..master_key.bucket_session import BucketSession

if TYPE_CHECKING:
    from .....domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext


def derive_test_bucket_key(identity: str, *, purpose: str) -> bytes:
    """Derive one deterministic, purpose-separated 32-byte test key."""
    return sha256(f"cadrumo-test-bucket:{purpose}:{identity}".encode("ascii")).digest()


def _profile_authority_contexts() -> tuple[ProfileCreateContext, ProfileDecodeContext]:
    """Return create/decode contexts from one bundled authority generation."""
    authority = bundled_authority()
    return authority.profile_create_context(), authority.profile_decode_context()


def new_test_profile_custody_envelope(profile_id: UUID) -> ProfileCustodyEnvelope:
    """Build deterministic custody material for one test profile identity."""
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


@contextmanager
def test_profile_recovery_envelope(
    profile_id: UUID,
    *,
    dek: bytes,
    dek_epoch: str,
) -> Generator[ProfileCustodyRecoveryEnvelopePort]:
    """Mint a production recovery wrapper and bound its secret lifetime."""
    enrollment = mint_profile_creation_recovery(profile_id=profile_id, dek=dek, dek_epoch=dek_epoch)
    try:
        yield enrollment.envelope
    finally:
        enrollment.recovery_key.wipe()


def publish_test_profile_capsule(
    profile_id: str | UUID,
    *,
    label: str,
    root: Path | None = None,
) -> UserProfileRecord:
    """Publish one incomplete test profile through the production lifecycle."""
    identity = UUID(canonical_profile_bucket_id(profile_id))
    storage_root = effective_storage_root(root)
    dek = derive_test_bucket_key(str(identity), purpose="dek")
    envelope = new_test_profile_custody_envelope(identity)
    create_context, decode_context = _profile_authority_contexts()
    initial = create_user_profile_record(
        context=create_context,
        profile_id=str(identity),
        setup_state=ProfileSetupState.INCOMPLETE,
    )
    session = ProfileRecordSession.from_envelope(
        envelope=envelope,
        dek=dek,
        profile_decode_context=decode_context,
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


def provision_test_profile_bucket_session(
    *,
    bucket_id: str,
    label: str,
    storage_root: Path,
    opened_at: datetime,
) -> tuple[BucketSession, BucketPaths]:
    """Publish a real encrypted test bucket and open its bound session."""
    publish_test_profile_capsule(bucket_id, label=label, root=storage_root)
    paths = bucket_paths(storage_root, bucket_id)
    session = BucketSession.open(
        bucket_id=bucket_id,
        kek=derive_test_bucket_key(bucket_id, purpose="kek"),
        dek=derive_test_bucket_key(bucket_id, purpose="dek"),
        idle_minutes=15,
        opened_at=opened_at,
        storage_root=storage_root,
    )
    return session, paths


def _active_bucket_dek(profile_id: UUID) -> bytes:
    """Return the DEK for the active session serving ``profile_id``."""
    active = current_active_bucket_session()
    if not session_serves_bucket(active, str(profile_id)):
        raise RuntimeError("profile-record test setup requires the target's active bucket session")
    return active.dek


@contextmanager
def open_test_profile_session(profile_id: str | UUID) -> Generator[str]:
    """Open one real bucket session for capsule-backed integration tests."""
    identity = str(UUID(str(profile_id)))
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
    material = load_committed_profile_password_material(profile_id, root=root)
    _, decode_context = _profile_authority_contexts()
    return ProfileRecordSession.from_envelope(
        envelope=material.envelope,
        dek=_active_bucket_dek(profile_id),
        profile_decode_context=decode_context,
    )


def _rebuild_record(
    record: UserProfileRecord,
    *,
    create_context: ProfileCreateContext,
    **updates: object,
) -> UserProfileRecord:
    """Recreate a fixture record through its pinned profile authority."""
    payload = record.model_dump()
    payload.pop("content_digest", None)
    payload.update(updates)
    return create_user_profile_record(
        context=create_context,
        profile_id=str(payload["profile_id"]),
        facts=payload["facts"],
        setup_state=payload["setup_state"],
        record_revision=payload["record_revision"],
        previous_record_digest=payload["previous_record_digest"],
        created_at=payload["created_at"],
        updated_at=payload["updated_at"],
    )


@contextmanager
def bound_test_profile_record(
    profile_id: str | UUID,
    *,
    root: Path | None = None,
) -> Generator[ProfileRecordRepository]:
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
    """CAS-replace a seeded record's facts and setup state through production doors."""
    identity = UUID(str(record.profile_id))
    storage_root = effective_storage_root(root)
    with bound_test_profile_record(identity, root=storage_root) as repository:
        current = repository.load(identity)
        replacement = _rebuild_record(
            record,
            create_context=repository.session.create_context(),
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
    """Merge facts onto a seeded record through the production capsule writer."""
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
    """Merge facts onto the active profile's seeded record."""
    active = resolve_active_bucket_id()
    if active is None:
        raise RuntimeError("no active profile is selected; seed and select one before setting facts")
    return upsert_test_profile_facts(active, facts, root=root)


def _facts_with_tax_id(tax_id: str) -> tuple[UserProfileFact, ...]:
    """Return the modelo readiness baseline under a different taxpayer id."""
    return tuple(
        UserProfileFact(path="identity.tax_id", value=tax_id) if fact.path == "identity.tax_id" else fact
        for fact in MODELO_READY_PROFILE_FACTS
    )


def seed_modelo_ready_profile_record(
    profile_id: str, *, clock: datetime, tax_id: str | None = None
) -> UserProfileRecord:
    """Seed one profile carrying the modelo readiness baseline."""
    create_context, _ = _profile_authority_contexts()
    return seed_test_profile_record(
        create_user_profile_record(
            context=create_context,
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=profile_id,
            facts=_facts_with_tax_id(tax_id) if tax_id else MODELO_READY_PROFILE_FACTS,
            created_at=clock,
            updated_at=clock,
        )
    )


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
        create_context, decode_context = _profile_authority_contexts()
        session = ProfileRecordSession.from_envelope(
            envelope=envelope,
            dek=dek,
            profile_decode_context=decode_context,
        )
        initial = _rebuild_record(
            record,
            create_context=create_context,
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


__all__ = [
    "bound_test_profile_record",
    "derive_test_bucket_key",
    "load_test_profile_record",
    "mint_test_profile_recovery_envelope",
    "new_test_profile_custody_envelope",
    "open_test_profile_session",
    "provision_test_profile_bucket_session",
    "publish_test_profile_capsule",
    "seed_modelo_ready_profile_record",
    "seed_test_profile_record",
    "set_active_test_profile_facts",
    "test_profile_recovery_envelope",
    "upsert_test_profile_facts",
]
