from __future__ import annotations

import base64
from pathlib import Path
from uuid import UUID, uuid4

from ......core.config import SecretStoreBackend, Settings
from ......core.profile_publication import ProfilePublicationKind
from ...custody.capsule import publish_profile_custody_capsule
from ...custody.records import ProfileCustodyEnvelope, ProfileCustodyKdfParameters, ProfileCustodyWrappedDek
from ...custody.sentinel import create_profile_custody_sentinel

_CAPSULE_DEK = bytes(range(32))

# Stable bucket identities for the provider suites. A bucket id is a profile
# UUID: registration is proven by the published capsule named for it, so a
# non-UUID label can never name a registered bucket.
_ALPHA = "0a1a0000-0000-4000-8000-000000000001"
_TORN = "0a1a0000-0000-4000-8000-000000000002"
_CURRENT = "0a1a0000-0000-4000-8000-000000000003"
_MISSING = "0a1a0000-0000-4000-8000-000000000004"
_ORPHANED = "0a1a0000-0000-4000-8000-000000000005"
_SHORT_IDLE = "0a1a0000-0000-4000-8000-000000000006"
_SHORT_CAP = "0a1a0000-0000-4000-8000-000000000007"
_DEFAULT_CAP = "0a1a0000-0000-4000-8000-000000000008"
_PROVIDER_REOPEN = "0a1a0000-0000-4000-8000-000000000009"
_PROVIDER_READ_CONCURRENCY = "0a1a0000-0000-4000-8000-00000000000a"


def _publish_registration_capsule(root: Path, bucket_id: str) -> None:
    """Publish the capsule that makes ``bucket_id`` a registered bucket."""
    profile_id = UUID(bucket_id)
    envelope = ProfileCustodyEnvelope.create(
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
    publish_profile_custody_capsule(
        profile_id=profile_id,
        transaction_id=uuid4(),
        publication_kind=ProfilePublicationKind.ENROLL,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_CAPSULE_DEK),
        data_files={},
        settings=Settings(cadrumo_local_storage_root=root),
    )


def _settings_with_store(tmp_path: Path, backend: SecretStoreBackend) -> Settings:
    return Settings(
        cadrumo_local_storage_root=tmp_path / "state",
        cadrumo_secret_store_dir=tmp_path / "fallback-store",
        cadrumo_secret_store_backend=backend,
    )


def _write_registered_bucket(root: Path, bucket_id: str) -> None:
    """Register a bucket the way production does: publish its capsule, nothing else.

    This wrote a plaintext manifest beside the capsule until that format was
    retired. Nothing in production ever read it back, so provisioning one here
    handed the tests a surface the application does not have.
    """
    # Publication owns the bucket directory: it arrives by the capsule's
    # no-replace rename, never by provisioning it first.
    _publish_registration_capsule(root, bucket_id)
