"""Recipient fingerprint registry for review-package recipient encryption.

This module lets a taxpayer record who they trust to receive an
encrypted review package -- an accountant or gestor -- by the SHA-256
fingerprint of that recipient's X25519 public key, verified out-of-band
(read aloud, compared over a separate channel) before it is trusted.
It is the taxpayer-side companion to
:mod:`~application.modelo._review_package_recipient_encryption`,
which consumes a registered recipient's public key to seal a review
package so only that recipient's matching private key can open it.

This registry never stores a private key of any kind: it is exclusively
a record of OTHER PEOPLE's public keys, mirroring how a real address
book of trusted correspondents works. The taxpayer's own encryption
keypair (needed only for a future reverse flow, where an accountant
encrypts feedback back to the taxpayer) is out of scope for this
module.

Persistence follows the exact shape of
:class:`~adapters.persistence.profile.bienes_inversion.BienesInversionIvaRegisterRepository`:
one ``FINANCIAL``-sensitivity secure-object singleton per bucket, an
empty register when absent, and duplicate-``recipient_id`` refusal on
add.

The encrypted row's storage policy is governed by
:class:`~adapters.persistence.storage.SensitivityClass`; this registry stores
public-key trust records at ``FINANCIAL`` sensitivity, never private key
material.

See Also:
    :mod:`~application.modelo._review_package_recipient_encryption`
        Consumes a registered recipient's public key to encrypt a
        review package.
    :mod:`~application.modelo._review_package_signing`
        Sibling per-profile keypair primitive (Ed25519, signature-only)
        this module's X25519 keypair concept deliberately does not
        share key material with -- signing and encryption keys must
        not be reused across purposes.
    :class:`~adapters.persistence.profile.bienes_inversion.BienesInversionIvaRegisterRepository`
        The structural template this repository mirrors.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
from pydantic import BaseModel, Field, model_validator

from ...adapters.persistence.storage._secure_object_namespaces import (
    MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE as _NAMESPACE,
)
from ...adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_bucket,
)
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import UTF_8_ENCODING as _UTF_8_ENCODING
from ...core.hashing import sha256_hex
from ...core.hex import HEX_PATTERN_64 as _HEX_PATTERN_64
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.time.clock import now as _utc_now

if TYPE_CHECKING:
    from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

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

    ``recipient_id`` is the register's natural key: :meth:`
    RecipientFingerprintRegistryRepository.get` resolves a recipient by it, and
    the resolved record supplies the public key a package is sealed to.
    """

    model_config = _STRICT_FROZEN

    records: tuple[RecipientFingerprintRecord, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _enforce_unique_recipient_ids(self) -> RecipientFingerprintRegister:
        """Refuse a register carrying two records under one ``recipient_id``.

        :meth:`RecipientFingerprintRegistryRepository.add` already refuses a
        duplicate against the register it just loaded, but that guards only the
        write path. A register that reaches storage with two records for the same
        id -- by any route -- was accepted on load, and ``get`` then returns
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


class RecipientFingerprintRegistryRepository:
    """Governed repository for the encrypted recipient-fingerprint register.

    The singleton row is owned by
    :data:`~adapters.persistence.storage.MODELO_REVIEW_PACKAGE_RECIPIENT_FINGERPRINT_REGISTRY_NAMESPACE`
    and persisted through
    :class:`~adapters.persistence.storage.SecureObjectRepository`, mirroring
    :class:`~adapters.persistence.profile.bienes_inversion.BienesInversionIvaRegisterRepository`.
    """

    def __init__(
        self,
        *,
        bucket_id: str | None = None,
        objects: SecureObjectRepository | None = None,
    ) -> None:
        """Initialise the repository.

        Args:
            bucket_id: Explicit bucket to bind to, resolved through
                :func:`~adapters.persistence.storage.secure_object_repository_for_bucket`.
                Ignored when ``objects`` is supplied.
            objects: Explicit
                :class:`~adapters.persistence.storage.SecureObjectRepository`
                override
                (tests). When neither ``objects`` nor ``bucket_id`` is
                supplied, defaults to the active-bucket secure object
                store.
        """
        if objects is not None:
            self._objects = objects
        elif bucket_id is not None:
            self._objects = secure_object_repository_for_bucket(bucket_id)
        else:
            self._objects = secure_object_repository_for_active_bucket()

    def load(self) -> RecipientFingerprintRegister:
        """Load the register, returning an empty register when absent.

        Raises:
            RecipientFingerprintRegistryError: When the envelope exists
                but the filesystem I/O itself fails.
            DecryptionError: When the envelope exists but its ciphertext
                fails AEAD authentication (tampered or corrupted at
                rest) -- propagated verbatim rather than re-wrapped, so
                a caller can distinguish "this register was tampered
                with" from a generic I/O failure. This is the anti-
                tautology proof this repository's roundtrip tests
                require: a corrupted on-disk payload must be refused
                loudly, not silently coerced into a plausible-looking
                empty register.
        """
        try:
            record = self._objects.load(
                _NAMESPACE.namespace,
                self._object_key,
                expected_class=_NAMESPACE.sensitivity,
                max_supported_version=_NAMESPACE.schema_version,
            )
            if record is None:
                return RecipientFingerprintRegister()
            return RecipientFingerprintRegister.model_validate_json(record.payload.decode(_UTF_8_ENCODING))
        except OSError as exc:
            raise RecipientFingerprintRegistryError(
                f"unable to load recipient fingerprint register: {self._object_key}",
                context={"namespace": _NAMESPACE.namespace, "object_key": self._object_key},
                translated_message="application.modelo.errors.recipient_registry_load_failed",
            ) from exc

    def list(self) -> tuple[RecipientFingerprintRecord, ...]:
        """Return every registered recipient record."""
        return self.load().records

    def get(self, recipient_id: str) -> RecipientFingerprintRecord:
        """Return the record for ``recipient_id``.

        Raises:
            RecipientNotRegisteredError: If no record with that id exists.
        """
        for existing in self.load().records:
            if existing.recipient_id == recipient_id:
                return existing
        raise RecipientNotRegisteredError(
            f"no recipient registered under id {recipient_id!r}",
            context={"recipient_id": recipient_id},
            translated_message="application.modelo.errors.recipient_registry_not_found",
        )

    def add(
        self,
        *,
        recipient_id: str,
        public_key_hex: str,
        label: str = "",
        added_at: datetime | None = None,
    ) -> RecipientFingerprintRegister:
        """Atomically add a recipient record and refuse a duplicate id.

        Args:
            recipient_id: Stable operator-chosen label (e.g.
                ``"my-accountant"``). Must be unique within the
                register.
            public_key_hex: The recipient's raw 32-byte X25519 public
                key, hex-encoded (see :func:`public_key_hex_from_raw_bytes`).
            label: Optional free-text display name.
            added_at: Optional override for the record's ``added_at``
                timestamp (tests only); defaults to the current UTC
                time.

        Raises:
            RecipientAlreadyRegisteredError: When a record with the
                same ``recipient_id`` already exists.
        """
        current = self.load()
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
        self._save_unlocked(updated)
        return updated

    def remove(self, recipient_id: str) -> RecipientFingerprintRegister:
        """Atomically remove the record for ``recipient_id``.

        Raises:
            RecipientNotRegisteredError: When no record with that id
                exists.
        """
        current = self.load()
        remaining = tuple(existing for existing in current.records if existing.recipient_id != recipient_id)
        if len(remaining) == len(current.records):
            raise RecipientNotRegisteredError(
                f"no recipient registered under id {recipient_id!r}",
                context={"recipient_id": recipient_id},
                translated_message="application.modelo.errors.recipient_registry_not_found",
            )
        updated = RecipientFingerprintRegister(records=remaining)
        self._save_unlocked(updated)
        return updated

    def _save_unlocked(self, register: RecipientFingerprintRegister) -> None:
        self._objects.save(
            namespace=_NAMESPACE.namespace,
            object_key=self._object_key,
            classification=_NAMESPACE.sensitivity,
            schema_version=_NAMESPACE.schema_version,
            written_at=_utc_now(),
            payload=register.model_dump_json().encode(_UTF_8_ENCODING),
            write_provenance="application.modelo.review_package_recipient_registry",
        )

    @property
    def _object_key(self) -> str:
        return _NAMESPACE.require_default_object_key()


__all__ = [
    "RecipientAlreadyRegisteredError",
    "RecipientFingerprintRecord",
    "RecipientFingerprintRegister",
    "RecipientFingerprintRegistryError",
    "RecipientFingerprintRegistryRepository",
    "RecipientNotRegisteredError",
    "public_key_hex_from_raw_bytes",
]
