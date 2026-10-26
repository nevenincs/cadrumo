"""Application use-case boundary for recipient-encrypted review packages.

The recipient-encryption capability is defined in
:mod:`cadrumo.application.modelo.recipient_encryption`.  This module keeps the
application-level errors and the use-case-shaped wrappers; the concrete
persistence and cryptographic implementation is supplied by an outer adapter.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ...core.errors.hierarchy import CadrumoError

if TYPE_CHECKING:
    from .recipient_encryption import (
        RecipientDecryptedPackage,
        RecipientEncryptedPackage,
        RecipientEncryptionCapability,
        RecipientEncryptionKeypair,
    )


class RecipientEncryptionError(CadrumoError):
    """Base error for review-package recipient-encryption failures."""


class RecipientDecryptionError(RecipientEncryptionError):
    """Raised when a recipient-encrypted package cannot be opened."""


class RecipientPackageExpiredError(RecipientDecryptionError):
    """Raised when an envelope is presented at or after its validity deadline."""


def ensure_recipient_encryption_keypair(
    *,
    bucket_id: str,
    recipient_encryption: RecipientEncryptionCapability,
    generated_at: datetime | None = None,
) -> RecipientEncryptionKeypair:
    """Return the bucket's recipient-encryption keypair through its capability."""
    return recipient_encryption.ensure_keypair(bucket_id=bucket_id, generated_at=generated_at)


def encrypt_review_package_for_recipient(
    package_bytes: bytes,
    *,
    recipient_public_key_hex: str,
    recipient_encryption: RecipientEncryptionCapability,
    review_only: bool = False,
    valid_for: timedelta | None = None,
    issued_at: datetime | None = None,
) -> RecipientEncryptedPackage:
    """Seal package bytes through the composed recipient-encryption capability."""
    return recipient_encryption.encrypt(
        package_bytes,
        recipient_public_key_hex=recipient_public_key_hex,
        review_only=review_only,
        valid_for=valid_for,
        issued_at=issued_at,
    )


def decrypt_review_package_for_recipient(
    envelope: RecipientEncryptedPackage,
    *,
    recipient_private_key_hex: str,
    recipient_encryption: RecipientEncryptionCapability,
    now: datetime | None = None,
) -> RecipientDecryptedPackage:
    """Open an envelope through the composed recipient-encryption capability."""
    return recipient_encryption.decrypt(
        envelope,
        recipient_private_key_hex=recipient_private_key_hex,
        now=now,
    )


__all__ = [
    "RecipientDecryptionError",
    "RecipientEncryptionError",
    "RecipientPackageExpiredError",
    "decrypt_review_package_for_recipient",
    "encrypt_review_package_for_recipient",
    "ensure_recipient_encryption_keypair",
]
