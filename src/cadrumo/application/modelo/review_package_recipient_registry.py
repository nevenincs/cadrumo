"""Recipient fingerprint registry for review-package recipient encryption.

This module lets a taxpayer record who they trust to receive an
encrypted review package -- an accountant or gestor -- by the SHA-256
fingerprint of that recipient's X25519 public key, verified out-of-band
(read aloud, compared over a separate channel) before it is trusted.
It is the taxpayer-side companion to
:mod:`~application.modelo.review_package_recipient_encryption`,
which consumes a registered recipient's public key to seal a review
package so only that recipient's matching private key can open it.

This registry never stores a private key of any kind: it is exclusively
a record of OTHER PEOPLE's public keys, mirroring how a real address
book of trusted correspondents works. The taxpayer's own encryption
keypair (needed only for a future reverse flow, where an accountant
encrypts feedback back to the taxpayer) is out of scope for this
module.

Persistence is supplied through a required application-owned registry
capability. The outward adapter binds that capability to one
``FINANCIAL``-sensitivity secure-object singleton per bucket, returning an
empty register when absent. Duplicate-``recipient_id`` refusal remains
application policy, and the registry stores public-key trust records only,
never private key material.

See Also:
    :mod:`~application.modelo.review_package_recipient_encryption`
        Consumes a registered recipient's public key to encrypt a
        review package.
    :mod:`~application.modelo.review_package_signing`
        Sibling per-profile keypair primitive (Ed25519, signature-only)
        this module's X25519 keypair concept deliberately does not
        share key material with -- signing and encryption keys must
        not be reused across purposes.
    :class:`~application.modelo.review_package_recipient_registry_ports.RecipientFingerprintRegistryPorts`
        Required persistence capability supplied by composition.
"""

from __future__ import annotations

from datetime import datetime
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import sha256_hex
from ...core.hex import HEX_PATTERN_64 as _HEX_PATTERN_64
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now as _utc_now
from .review_package_recipient_registry_ports import RecipientFingerprintRegistryPorts

#: Raw X25519 public key size in bytes (RFC 7748).
_X25519_PUBLIC_KEY_BYTES = 32


class RecipientFingerprintRegistryError(CadrumoError):
    """Base error for recipient-fingerprint registry failures."""


class RecipientAlreadyRegisteredError(RecipientFingerprintRegistryError):
    """Raised when ``add`` is called with a ``recipient_id`` already on file."""


class RecipientNotRegisteredError(RecipientFingerprintRegistryError):
    """Raised when ``remove`` or a lookup names a ``recipient_id`` not on file."""


class RecipientFingerprintRecord(BaseModel):
    """One trusted recipient's public encryption key on file.

    ``public_key_hex`` is the recipient's raw 32-byte X25519 public key
    (RFC 7748), hex-encoded. ``fingerprint_sha256`` is a plain (non-
    persisted) property -- SHA-256 of the raw public key bytes,
    hex-encoded -- so it can never drift from the key it fingerprints
    and never needs to round-trip through the strict-extra-forbid
    persistence boundary; it exists purely for a human-readable
    out-of-band verification string (the taxpayer reads it aloud to /
    compares it against a value the accountant reads from their own key
    export).
    """

    model_config = _STRICT_FROZEN

    recipient_id: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=200)
    public_key_hex: str = Field(pattern=_HEX_PATTERN_64)
    added_at: datetime

    @property
    def fingerprint_sha256(self) -> str:
        """SHA-256 hex digest of the raw public key bytes, for out-of-band display."""
        return sha256_hex(bytes.fromhex(self.public_key_hex))

    def public_key(self) -> X25519PublicKey:
        """Reconstruct the live :class:`X25519PublicKey` from stored raw bytes."""
        return X25519PublicKey.from_public_bytes(bytes.fromhex(self.public_key_hex))


class RecipientFingerprintRegister(BaseModel):
    """A bucket's full set of trusted recipient fingerprint records.

    ``recipient_id`` is the register's natural key: the application lookup
    service resolves a recipient by it, and the resolved record supplies the
    public key a package is sealed to.
    """

    model_config = _STRICT_FROZEN

    records: tuple[RecipientFingerprintRecord, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _enforce_unique_recipient_ids(self) -> RecipientFingerprintRegister:
        """Refuse a register carrying two records under one ``recipient_id``.

        The application add operation already refuses a duplicate against the
        register it just loaded, but that guards only the write path. A register
        that reaches storage with two records for the same id -- by any route --
        was accepted on load, and lookup then returns
        whichever comes first in the tuple. Recipient encryption would depend on
        row order rather than on one canonical trusted key, and the operator who
        verified a fingerprint out of band would have no way to tell which key
        their package was actually sealed to.

        Enforcing it on the model puts the refusal at every boundary the model
        crosses, including hydration from the encrypted row, rather than only at
        the one call site that happened to check.
        """
        seen: set[str] = set()
        duplicates: set[str] = set()
        for record in self.records:
            if record.recipient_id in seen:
                duplicates.add(record.recipient_id)
            seen.add(record.recipient_id)
        if duplicates:
            listed = ", ".join(sorted(repr(value) for value in duplicates))
            raise ValueError(f"recipient_id must be unique in a fingerprint register; duplicated: {listed}")
        return self


def public_key_hex_from_raw_bytes(raw_public_key: bytes) -> str:
    """Validate and hex-encode a raw X25519 public key.

    Args:
        raw_public_key: Exactly 32 raw bytes (RFC 7748 encoding).

    Raises:
        RecipientFingerprintRegistryError: If ``raw_public_key`` is not
            exactly 32 bytes, or is not a well-formed X25519 point.
    """
    if len(raw_public_key) != _X25519_PUBLIC_KEY_BYTES:
        raise RecipientFingerprintRegistryError(
            f"X25519 public key must be {_X25519_PUBLIC_KEY_BYTES} bytes, got {len(raw_public_key)}",
            translated_message="application.modelo.errors.recipient_registry_invalid_public_key",
            context={"length": str(len(raw_public_key))},
        )
    # Round-trips through the cryptography library to reject a malformed point.
    X25519PublicKey.from_public_bytes(raw_public_key)
    return raw_public_key.hex()


def list_recipient_fingerprints(
    *,
    ports: RecipientFingerprintRegistryPorts,
) -> tuple[RecipientFingerprintRecord, ...]:
    """Return every trusted recipient through the required registry capability."""
    return ports.registry_repository.load().records


def get_recipient_fingerprint(
    recipient_id: str,
    *,
    ports: RecipientFingerprintRegistryPorts,
) -> RecipientFingerprintRecord:
    """Resolve one trusted recipient or raise the application lookup refusal."""
    for existing in ports.registry_repository.load().records:
        if existing.recipient_id == recipient_id:
            return existing
    raise RecipientNotRegisteredError(
        f"no recipient registered under id {recipient_id!r}",
        context={"recipient_id": recipient_id},
        translated_message="application.modelo.errors.recipient_registry_not_found",
    )


def add_recipient_fingerprint(
    *,
    recipient_id: str,
    public_key_hex: str,
    ports: RecipientFingerprintRegistryPorts,
    label: str = "",
    added_at: datetime | None = None,
) -> RecipientFingerprintRegister:
    """Add a trusted recipient, refusing duplicate ids before persistence."""
    current = ports.registry_repository.load()
    if any(existing.recipient_id == recipient_id for existing in current.records):
        raise RecipientAlreadyRegisteredError(
            f"recipient {recipient_id!r} is already registered",
            context={"recipient_id": recipient_id},
            translated_message="application.modelo.errors.recipient_registry_already_exists",
        )
    record = RecipientFingerprintRecord(
        recipient_id=recipient_id,
        label=label,
        public_key_hex=public_key_hex,
        added_at=added_at or _utc_now(),
    )
    updated = RecipientFingerprintRegister(records=(*current.records, record))
    ports.registry_repository.save(updated)
    return updated


def remove_recipient_fingerprint(
    recipient_id: str,
    *,
    ports: RecipientFingerprintRegistryPorts,
) -> RecipientFingerprintRegister:
    """Remove one trusted recipient, refusing an unknown id."""
    current = ports.registry_repository.load()
    remaining = tuple(existing for existing in current.records if existing.recipient_id != recipient_id)
    if len(remaining) == len(current.records):
        raise RecipientNotRegisteredError(
            f"no recipient registered under id {recipient_id!r}",
            context={"recipient_id": recipient_id},
            translated_message="application.modelo.errors.recipient_registry_not_found",
        )
    updated = RecipientFingerprintRegister(records=remaining)
    ports.registry_repository.save(updated)
    return updated


__all__ = [
    "RecipientAlreadyRegisteredError",
    "RecipientFingerprintRecord",
    "RecipientFingerprintRegister",
    "RecipientFingerprintRegistryError",
    "RecipientNotRegisteredError",
    "add_recipient_fingerprint",
    "get_recipient_fingerprint",
    "list_recipient_fingerprints",
    "public_key_hex_from_raw_bytes",
    "remove_recipient_fingerprint",
]
