"""Secure-object adapter for review-package signing keypairs."""

from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError

from ....application.modelo.review_package_signing import ReviewPackageSigningError, ReviewPackageSigningKeypair
from ....application.modelo.review_package_signing_ports import ReviewPackageSigningKeypairCapability
from ....core.ed25519_signing import generate_ed25519_keypair_hex
from ....core.identity.bucket import canonical_bucket_id
from ....core.time.clock import now as _utc_now
from ..storage.errors import StorageError
from ..storage.runtime_repository import secure_object_repository_for_bucket
from ..storage.secure_object_namespaces import MODELO_REVIEW_PACKAGE_SIGNING_KEY_NAMESPACE as _NAMESPACE
from ..storage.sql.secure_objects import SecureObjectRepository
from ._review_package_keypair import ensure_singleton_keypair


def _signing_key_object_key(bucket_id: str) -> str:
    """Return the namespace-owned natural key for one bucket's keypair."""
    return f"review-package-signing-key:{canonical_bucket_id(bucket_id)}"


class ReviewPackageSigningKeypairAdapter:
    """Concrete signing-keypair capability backed by encrypted storage."""

    def __init__(self, *, repository: SecureObjectRepository, bucket_id: str) -> None:
        """Bind signing-key storage to one canonical bucket."""
        self._repository = repository
        self._bucket_id = canonical_bucket_id(bucket_id)

    def ensure_keypair(
        self,
        *,
        bucket_id: str,
        generated_at: datetime | None = None,
    ) -> ReviewPackageSigningKeypair:
        """Load or atomically mint the signing keypair for ``bucket_id``."""
        normalized_bucket_id = canonical_bucket_id(bucket_id)
        if normalized_bucket_id != self._bucket_id:
            raise ReviewPackageSigningError(
                "review-package signing capability is bound to a different bucket",
            )

        def _generate() -> ReviewPackageSigningKeypair:
            minted = generate_ed25519_keypair_hex()
            return ReviewPackageSigningKeypair(
                bucket_id=normalized_bucket_id,
                private_key_hex=minted.private_key_hex,
                public_key_hex=minted.public_key_hex,
                created_at=generated_at or _utc_now(),
            )

        def _mismatch_error() -> ReviewPackageSigningError:
            return ReviewPackageSigningError(
                "stored review-package signing keypair does not belong to the bucket it was read from",
            )

        try:
            return ensure_singleton_keypair(
                repository=self._repository,
                namespace=_NAMESPACE,
                object_key=_signing_key_object_key(normalized_bucket_id),
                model_type=ReviewPackageSigningKeypair,
                generate=_generate,
                bucket_id_of=lambda keypair: keypair.bucket_id,
                created_at_of=lambda keypair: keypair.created_at,
                expected_bucket_id=normalized_bucket_id,
                mismatch_error=_mismatch_error,
                write_provenance="adapters.persistence.profile.review_package_signing",
            )
        except ReviewPackageSigningError:
            raise
        except (OSError, StorageError, TypeError, ValueError, ValidationError) as exc:
            raise ReviewPackageSigningError(
                "unable to load or persist review-package signing keypair",
            ) from exc


def build_review_package_signing_keypair_capability(
    *,
    bucket_id: str,
) -> ReviewPackageSigningKeypairCapability:
    """Bind the signing-keypair capability to the secure store for ``bucket_id``."""
    normalized_bucket_id = canonical_bucket_id(bucket_id)
    return ReviewPackageSigningKeypairAdapter(
        repository=secure_object_repository_for_bucket(normalized_bucket_id),
        bucket_id=normalized_bucket_id,
    )


__all__ = [
    "ReviewPackageSigningKeypairAdapter",
    "build_review_package_signing_keypair_capability",
]
