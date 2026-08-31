"""Concrete profile-capsule runtime composition for persistence-backed tests."""

from __future__ import annotations

from base64 import b64encode
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from .....application.user_profile.capsule_record import ProfileRecordSession
from .....application.user_profile.custody_ports import ProfileCustodyRecoveryEnvelopePort
from .....application.user_profile.lifecycle import ProfileCapsuleLifecycle
from .....application.user_profile.recovery_custody import mint_profile_creation_recovery
from .....core.identity import canonical_profile_bucket_id
from .....core.paths import effective_storage_root
from .....domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ..bucket._layout import BucketPaths, bucket_paths
from ..custody.records import ProfileCustodyEnvelope, ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from ..custody.sentinel import create_profile_custody_sentinel
from ..master_key.bucket_session import BucketSession


def derive_test_bucket_key(identity: str, *, purpose: str) -> bytes:
    """Derive one deterministic, purpose-separated 32-byte test key."""
    return sha256(f"cadrumo-test-bucket:{purpose}:{identity}".encode("ascii")).digest()


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
) -> Iterator[ProfileCustodyRecoveryEnvelopePort]:
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
    initial = UserProfileRecord(profile_id=str(identity), setup_state=ProfileSetupState.INCOMPLETE)
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
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


__all__ = [
    "derive_test_bucket_key",
    "new_test_profile_custody_envelope",
    "provision_test_profile_bucket_session",
    "publish_test_profile_capsule",
    "test_profile_recovery_envelope",
]
