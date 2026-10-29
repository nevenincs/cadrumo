"""Neutral profile record encryption contracts and persistence-provider refusals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CoreError
from ...core.models import STRICT_FROZEN_CONFIG


class ProfileRecordCryptoError(CoreError):
    """The configured profile-record crypto provider rejected an operation.

    Roots at :class:`~core.errors.hierarchy.CoreError` so the refusal binds to the error
    registry rather than reaching an operator as an unregistered builtin. The
    port deliberately does not root at the persistence layer's own
    :exc:`~adapters.persistence.storage.errors.EncryptionError`: this package exists
    to keep the adapter's crypto types off the application port, and adopting
    that family would make the port's refusal catchable by every storage-family
    handler — a broadening, not a re-root. :exc:`RuntimeError` is retained so
    the ancestry every existing caller was written against is unchanged.
    """


class ProfileCustodyRecordIntegrityError(CoreError):
    """The persistence provider refused a malformed or altered custody record."""


class ProfileCustodyConcurrentChangeError(ProfileCustodyRecordIntegrityError):
    """A capsule changed generation between two reads of one observation.

    Narrower than its parent on purpose: the store is not damaged, the caller
    simply lost a race with a publication or a deletion.  A listing that
    reports this is telling the operator to look again, not to repair.
    """


class ProfileRecordEncryptedBlob(BaseModel):
    """Neutral encrypted-record shape exchanged across the application port."""

    model_config = STRICT_FROZEN_CONFIG

    nonce: bytes = Field(min_length=12, max_length=12)
    ciphertext: bytes = Field(min_length=16)

    def to_wire(self) -> bytes:
        """Serialise the blob as its canonical nonce-plus-ciphertext bytes."""
        return self.nonce + self.ciphertext

    @classmethod
    def from_wire(cls, payload: bytes) -> ProfileRecordEncryptedBlob:
        """Parse the canonical wire representation without adapter imports."""
        minimum = 12 + 16
        if len(payload) < minimum:
            raise ProfileRecordCryptoError(
                f"AEAD payload too short: got {len(payload)} bytes, need at least {minimum}",
            )
        return cls(nonce=payload[:12], ciphertext=payload[12:])


@dataclass(frozen=True, slots=True)
class ProfilePassphraseKdfPolicy:
    """Supported Argon2id version and window for passphrase-sealed records."""

    version: int
    minimum_memory_cost_kib: int
    maximum_memory_cost_kib: int
    minimum_time_cost: int
    maximum_time_cost: int
    minimum_parallelism: int
    maximum_parallelism: int
    salt_bytes: int


@dataclass(frozen=True, slots=True)
class ProfilePassphraseKdfParameters:
    """Persisted KDF parameters accompanying one passphrase-sealed record."""

    version: int
    memory_cost: int
    time_cost: int
    parallelism: int
    salt: bytes


@dataclass(frozen=True, slots=True)
class ProfilePassphraseEncryptedRecord:
    """Neutral KDF metadata and AEAD ciphertext minted by persistence."""

    parameters: ProfilePassphraseKdfParameters
    blob: ProfileRecordEncryptedBlob


class ProfileRecordCryptoPort(Protocol):
    """AEAD and passphrase-sealing operations for profile-owned records."""

    def passphrase_kdf_policy(self) -> ProfilePassphraseKdfPolicy:
        """Return the single supported Argon2id version and cost window."""
        ...

    def passphrase_kdf_window_accepts(
        self,
        *,
        memory_cost: int,
        time_cost: int,
        parallelism: int,
        salt: bytes,
    ) -> bool:
        """Return whether persisted parameters satisfy the supported cost window."""
        ...

    def encrypt_record(
        self,
        plaintext: bytes,
        *,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> ProfileRecordEncryptedBlob:
        """Encrypt one record using authenticated associated data."""
        ...

    def decrypt_record(
        self,
        blob: ProfileRecordEncryptedBlob,
        *,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """Decrypt one record and verify its authenticated associated data."""
        ...

    def seal_with_passphrase(
        self,
        plaintext: bytes,
        *,
        passphrase: bytes,
        associated_data: bytes,
    ) -> ProfilePassphraseEncryptedRecord:
        """Derive a fresh passphrase key and seal one record under it."""
        ...
