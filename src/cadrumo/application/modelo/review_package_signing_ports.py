"""Application-owned keypair capability for review-package signing.

Signing policy and the keypair DTO remain application concerns.  The
bucket-scoped mint/load/persist operation is supplied by an outer composition
root so secure-object storage and its failure modes cannot enter the
application service.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .review_package_signing import ReviewPackageSigningKeypair


class ReviewPackageSigningKeypairCapability(Protocol):
    """Application-facing capability for one bucket's signing keypair."""

    def ensure_keypair(
        self,
        *,
        bucket_id: str,
        generated_at: datetime | None = None,
    ) -> ReviewPackageSigningKeypair:
        """Return or mint the bucket-scoped signing keypair."""
        ...


class ReviewPackageSigningKeypairCapabilityFactory(Protocol):
    """Construct a signing-keypair capability for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> ReviewPackageSigningKeypairCapability:
        """Return the capability for ``bucket_id``."""
        ...


__all__ = [
    "ReviewPackageSigningKeypairCapability",
    "ReviewPackageSigningKeypairCapabilityFactory",
]
