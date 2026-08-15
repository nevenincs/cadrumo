"""Application ports for custody records supplied to profile lifecycle actions."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from ...core import ProfileSessionRefusalReason, SecureObjectWrite
    from ...core.classification import SensitivityClass


class ProfileBucketSessionPort(Protocol):
    """Live bucket-session capability exposed across the application boundary."""

    @property
    def bucket_id(self) -> str:
        """The bucket this live session was opened against."""
        ...

    @property
    def dek(self) -> bytes:
        """The session's bound data-encryption key."""
        ...

    @property
    def idle_deadline(self) -> datetime:
        """The sliding deadline the next activity advances."""
        ...

    @property
    def absolute_deadline(self) -> datetime:
        """The immutable cap no activity can extend."""
        ...

    @property
    def opened_at(self) -> datetime:
        """When this session was authenticated."""
        ...

    @property
    def unsecured_backend(self) -> bool:
        """Whether the session was opened over the explicitly unsecured backend."""
        ...

    def touch(self, now: datetime) -> None:
        """Advance the sliding idle deadline."""
        ...

    def is_expired(self, now: datetime) -> bool:
        """Return whether this session has crossed either deadline."""
        ...

    def close(self) -> None:
        """Zeroise and retire this session's local key material."""
        ...


class ProfileCustodyPasswordMaterialPort(Protocol):
    """Normal-password material exposed by the custody read boundary.

    Every record-shaped port here declares its fields read-only.  The custody
    records these narrow are frozen, and a mutable protocol member is invariant,
    so a read-write declaration would make the real record unassignable to the
    very port that exists to narrow it.  Read-only is also the truthful shape:
    the application observes committed custody state, it never writes back
    through the narrowed view.
    """

    @property
    def envelope(self) -> ProfileCustodyEnvelopePort:
        """The committed password envelope for this profile."""
        ...

    @property
    def sentinel(self) -> ProfileCustodySentinelPort:
        """The committed DEK sentinel proving an unwrap succeeded."""
        ...


class ProfilePersistedSessionPort(Protocol):
    """Persisted session record fields needed by login orchestration."""

    @property
    def profile_id(self) -> UUID:
        """The profile this receipt accelerates."""
        ...

    @property
    def session_id(self) -> UUID:
        """The receipt's own identity."""
        ...

    @property
    def custody_generation(self) -> int:
        """The custody generation this receipt was minted against."""
        ...

    @property
    def dek_epoch(self) -> str:
        """The DEK epoch this receipt was minted against."""
        ...

    @property
    def issued_at(self) -> datetime:
        """When the receipt was minted."""
        ...

    @property
    def idle_deadline(self) -> datetime:
        """The sliding deadline a resume may advance."""
        ...

    @property
    def absolute_deadline(self) -> datetime:
        """The immutable cap no resume can extend."""
        ...


class ProfileSessionResumeOutcomePort(Protocol):
    """Fail-closed persisted-session evaluation result."""

    @property
    def resumed(self) -> bool:
        """Whether the persisted receipt was accepted."""
        ...

    @property
    def refusal(self) -> ProfileSessionRefusalReason | None:
        """The typed reason a resume was refused, if it was."""
        ...

    @property
    def record(self) -> ProfilePersistedSessionPort | None:
        """The evaluated receipt, present whether or not it was accepted."""
        ...


class ProfileCustodySecureObjectRawRowPort(Protocol):
    """Metadata and payload fields exposed by one secure-object row."""

    @property
    def namespace(self) -> str:
        """The registered namespace this row was written under."""
        ...

    @property
    def object_key(self) -> bytes:
        """The opaque digest addressing this row within its namespace."""
        ...

    @property
    def payload(self) -> bytes:
        """The row's stored ciphertext."""
        ...

    @property
    def revision_id(self) -> str | None:
        """The row's current CAS revision token."""
        ...

    @property
    def previous_revision_id(self) -> str | None:
        """The revision this row replaced."""
        ...

    @property
    def payload_hash(self) -> str | None:
        """The plaintext digest recorded at write time."""
        ...

    @property
    def ciphertext_hash(self) -> str | None:
        """The ciphertext digest recorded at write time."""
        ...

    @property
    def write_provenance(self) -> str | None:
        """The recorded origin of this row's most recent write."""
        ...

    @property
    def source_event_id(self) -> str | None:
        """The lifecycle event that produced this row, if any."""
        ...


class ProfileCustodySecureObjectRecordPort(Protocol):
    """Decrypted secure-object payload and its CAS revision token."""

    @property
    def revision_id(self) -> str:
        """The record's current CAS revision token."""
        ...

    @property
    def payload(self) -> bytes:
        """The decrypted record bytes."""
        ...


class ProfileCustodySecureObjectRepositoryPort(Protocol):
    """The small encrypted-object surface needed by a profile capsule."""

    def iter_all_records_raw(self) -> Iterator[ProfileCustodySecureObjectRawRowPort]:
        """Iterate rows without bypassing the repository's integrity checks."""
        ...

    def load(
        self,
        namespace: str,
        object_key: str,
        *,
        expected_class: SensitivityClass,
        max_supported_version: int,
    ) -> ProfileCustodySecureObjectRecordPort | None:
        """Load and decrypt one object under its registered namespace contract."""
        ...

    def apply_batch(self, writes: tuple[SecureObjectWrite, ...]) -> None:
        """Commit an atomic set of encrypted-object writes."""
        ...


class ProfileCustodyEnvelopePort(Protocol):
    """Opaque password-envelope contract accepted by custody transactions."""

    profile_id: UUID
    password_generation: int
    self_digest: str
    dek_epoch: str


class ProfileCustodySentinelPort(Protocol):
    """Opaque DEK-sentinel contract accepted by custody transactions."""

    profile_id: UUID


class ProfileCustodyRecoveryEnvelopePort(Protocol):
    """Recovery-envelope contract forwarded to custody storage.

    The two identity fields are declared because the application genuinely
    reads them: a recovery wrapper is only valid for the exact profile and
    DEK epoch it was minted against, and an enrollment that cannot be
    checked against the password envelope beside it is an enrollment nothing
    can prove belongs to this capsule. Everything else about the record --
    the KDF parameters, the wrapped key, the AAD descriptor -- stays opaque,
    because the application has no business reading key material.
    """

    profile_id: UUID
    dek_epoch: str


__all__ = [
    "ProfileBucketSessionPort",
    "ProfileCustodyEnvelopePort",
    "ProfileCustodyPasswordMaterialPort",
    "ProfileCustodyRecoveryEnvelopePort",
    "ProfileCustodySecureObjectRawRowPort",
    "ProfileCustodySecureObjectRecordPort",
    "ProfileCustodySecureObjectRepositoryPort",
    "ProfileCustodySentinelPort",
    "ProfilePersistedSessionPort",
    "ProfileSessionResumeOutcomePort",
]
