"""Application-owned contract for recipient-encrypted review packages.

The review-package use cases need one capability for three operations: minting
the bucket's recipient keypair, sealing bytes for a public key, and opening an
envelope with a private key.  The capability deliberately exposes only these
application DTOs and errors.  Its concrete implementation belongs to an
outward persistence/crypto adapter and is supplied by an executable
composition root.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import HEX_PATTERN_64 as _HEX_PATTERN_64
from ...core.identity.bucket import BucketId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.utc import UtcInstant

_RECIPIENT_ENCRYPTION_ENVELOPE_VERSION = 1


class RecipientEncryptionKeypair(BaseModel):
    """The transient, typed keypair payload owned by the application boundary.

    The adapter stores this payload through secure persistence.  Private and
    public key material remain hex strings here so the application contract
    does not expose a cryptography implementation type.
    """

    model_config = _STRICT_FROZEN

    bucket_id: BucketId
    private_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    created_at: UtcInstant


class RecipientEncryptedPackage(BaseModel):
    """Wire envelope for a review package sealed for one recipient."""

    model_config = _STRICT_FROZEN

    envelope_version: int = Field(default=_RECIPIENT_ENCRYPTION_ENVELOPE_VERSION, ge=1)
    ephemeral_public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    recipient_public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    ciphertext: bytes = Field(min_length=1)
    envelope_nonce_hex: str = Field(pattern=_HEX_PATTERN_64)
    issued_at: UtcInstant
    valid_until: UtcInstant | None = Field(default=None)
    review_only: bool = Field(default=False)

    @field_validator("ciphertext", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _ciphertext_accepts_hex_or_raw_bytes(cls, value: object) -> object:
        if isinstance(value, str):
            return bytes.fromhex(value)
        return value

    @field_serializer("ciphertext", when_used="json")
    def _ciphertext_as_hex_for_json(self, value: bytes) -> str:
        return value.hex()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _valid_until_is_after_issued_at(self) -> RecipientEncryptedPackage:
        if self.valid_until is not None and self.valid_until <= self.issued_at:
            raise ValueError("valid_until must be strictly after issued_at")
        return self


class RecipientDecryptedPackage(BaseModel):
    """Recovered package bytes plus the envelope's disposition flag."""

    model_config = _STRICT_FROZEN

    package_bytes: bytes = Field(min_length=1)
    review_only: bool


class RecipientEncryptionCapability(Protocol):
    """Application-facing recipient-encryption capability.

    Implementations may use persistence and cryptography internally, but they
    must translate those concrete DTOs and failures to this contract before
    returning or raising across the application boundary.
    """

    def ensure_keypair(
        self,
        *,
        bucket_id: str,
        generated_at: datetime | None = None,
    ) -> RecipientEncryptionKeypair:
        """Return or mint the bucket-scoped recipient keypair."""
        ...

    def encrypt(
        self,
        package_bytes: bytes,
        *,
        recipient_public_key_hex: str,
        review_only: bool = False,
        valid_for: timedelta | None = None,
        issued_at: datetime | None = None,
    ) -> RecipientEncryptedPackage:
        """Seal package bytes for one recipient public key."""
        ...

    def decrypt(
        self,
        envelope: RecipientEncryptedPackage,
        *,
        recipient_private_key_hex: str,
        now: datetime | None = None,
    ) -> RecipientDecryptedPackage:
        """Open one envelope with the recipient's private key material."""
        ...


class RecipientEncryptionCapabilityFactory(Protocol):
    """Construct a capability bound to one bucket's secure-object store."""

    def __call__(self, *, bucket_id: str) -> RecipientEncryptionCapability:
        """Return the capability used by one bucket-scoped invocation."""
        ...


__all__ = [
    "RecipientDecryptedPackage",
    "RecipientEncryptedPackage",
    "RecipientEncryptionCapability",
    "RecipientEncryptionCapabilityFactory",
    "RecipientEncryptionKeypair",
]
