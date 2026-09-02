"""Shared bucket registration for storage-lane tests.

A bucket root under ``buckets/`` comes into existence exactly once, by the
no-replace rename that publishes its profile capsule; the engine refuses every
other creator (see
:func:`~adapters.persistence.storage.sql.engine._refuse_absent_bucket_root`).
A fixture that materialises the directory tree directly builds a state no
production path can reach and occupies the destination publication must claim.

This module is the storage lane's one door onto that creating authority for
tests that need a *registered* bucket before any record exists. It calls the
production publication verbs directly -- there is no test-only bucket creator
-- and fixes the custody parameters so registration costs no key derivation.

Consolidated from the copy that lived in ``master_key/tests``; it follows the
same shared-plumbing precedent as :mod:`.engine_bootstrap`.
"""

from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

from .....core.config import Settings
from .....core.profile_publication import ProfilePublicationKind
from ..bucket.directory_layout import bucket_paths
from ..custody.capsule import publish_profile_custody_capsule
from ..custody.records import ProfileCustodyEnvelope, ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from ..custody.sentinel import create_profile_custody_sentinel

#: The data key the published sentinel is bound to. Tests that only need the
#: bucket to *exist* may bind any session key they like; tests that go on to
#: prove the sentinel opens must bind this one.
CAPSULE_DEK = bytes(range(32))


def registration_envelope(profile_id: UUID) -> ProfileCustodyEnvelope:
    """Return the fixed password envelope every registered test bucket carries.

    The KDF parameters are stated rather than calibrated: registration here
    proves a bucket exists, not that a passphrase unwraps, so measuring a cost
    grid per test would buy nothing and cost a supervised child process.
    """
    return ProfileCustodyEnvelope.create(
        profile_id=profile_id,
        password_generation=1,
        dek_epoch=base64.b64encode(b"e" * 16).decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=base64.b64encode(b"k" * 16).decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=base64.b64encode(b"n" * 12).decode("ascii"),
            ciphertext_b64=base64.b64encode(b"c" * 32).decode("ascii"),
            tag_b64=base64.b64encode(b"t" * 16).decode("ascii"),
        ),
    )


def publish_registration_capsule(root: Path, bucket_id: str) -> None:
    """Register ``bucket_id`` under ``root`` the way production does.

    Args:
        root: The local storage root the bucket is published beneath.
        bucket_id: The bucket's profile UUID. Registration is proven by the
            capsule named for it, so a non-UUID label can never name a
            registered bucket.
    """
    profile_id = UUID(bucket_id)
    envelope = registration_envelope(profile_id)
    publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=uuid4(),
        publication_kind=ProfilePublicationKind.ENROLL,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=CAPSULE_DEK),
        data_files={},
        settings=Settings(cadrumo_local_storage_root=root),
    )


def ensure_registered_bucket(root: Path, bucket_id: str) -> None:
    """Register ``bucket_id`` unless its bucket root is already published.

    Publication is deliberately no-replace, so a fixture that re-enters the
    same bucket span -- the ordinary shape of a test that switches to a second
    profile and back -- would be refused on the second entry. Existence of the
    bucket root is the same fact publication establishes, so consulting it is
    the guard rather than a second creator.
    """
    if bucket_paths(root, bucket_id).bucket_dir.exists():
        return
    publish_registration_capsule(root, bucket_id)


__all__ = [
    "CAPSULE_DEK",
    "ensure_registered_bucket",
    "publish_registration_capsule",
    "registration_envelope",
]
