"""Inward signing-capability fakes for application-layer tests."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ..review_package_signing import ReviewPackageSigningKeypair


class InMemoryReviewPackageSigningKeypairCapability:
    """Small application-bound fake with bucket-scoped singleton semantics."""

    def __init__(self) -> None:
        self._keypairs: dict[str, ReviewPackageSigningKeypair] = {}
        self._lock = Lock()

    def ensure_keypair(
        self,
        *,
        bucket_id: str,
        generated_at: datetime | None = None,
    ) -> ReviewPackageSigningKeypair:
        """Return one in-memory keypair per bucket without touching persistence."""
        with self._lock:
            existing = self._keypairs.get(bucket_id)
            if existing is not None:
                return existing
            private_key = Ed25519PrivateKey.generate()
            keypair = ReviewPackageSigningKeypair(
                bucket_id=bucket_id,
                private_key_hex=private_key.private_bytes_raw().hex(),
                public_key_hex=private_key.public_key().public_bytes_raw().hex(),
                created_at=generated_at or datetime.now(UTC),
            )
            self._keypairs[bucket_id] = keypair
            return keypair


__all__ = ["InMemoryReviewPackageSigningKeypairCapability"]
