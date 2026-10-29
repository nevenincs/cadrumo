"""Read-only custody record projections and their bounded storage capabilities."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol
from uuid import UUID

from ...core.classification.policies import SensitivityClass
from ...core.profile_publication import ProfilePublicationKindValue
from ...core.secure_object_write import SecureObjectWrite


class ProfileCustodyCommitPort(Protocol):
    """Publication identity exposed by one recognized profile capsule."""

    @property
    def transaction_id(self) -> UUID:
        """The transaction that durably published this capsule."""
        ...

    @property
    def publication_kind(self) -> ProfilePublicationKindValue:
        """Whether this capsule was enrolled locally or restored."""
        ...

    @property
    def published_at(self) -> str:
        """The canonical UTC instant recorded by the publication marker."""
        ...


class ProfileCustodyCapsuleLabelPort(Protocol):
    """Canonical label provenance exposed by physical custody storage."""

    @property
    def label(self) -> str:
        """The normalized operator-facing profile label."""
        ...

    @property
    def label_revision(self) -> int:
        """The revision of this label lineage."""
        ...

    @property
    def content_digest(self) -> str:
        """The digest of the label payload excluding derived digests."""
        ...

    @property
    def self_digest(self) -> str:
        """The digest authenticating the complete label record."""
        ...

    def canonical_json_bytes(self) -> bytes:
        """Return the canonical bytes committed into the capsule inventory."""
        ...


class ProfileCustodyCapsuleSummaryWitnessPort(Protocol):
    """One coherent, non-authenticating observation of a committed capsule.

    The commit and the label were read under a single filesystem anchor and
    proved to name the same UUID, so a consumer may join them without
    re-opening either record and without entering custody at all.
    """

    @property
    def profile_id(self) -> UUID:
        """The UUID proven independently by both observed records."""
        ...

    @property
    def commit(self) -> ProfileCustodyCommitPort:
        """The recognized current publication marker."""
        ...

    @property
    def label(self) -> ProfileCustodyCapsuleLabelPort:
        """The UUID-bound label provenance observed under the same anchor."""
        ...


class ProfileCustodyLabelHeadPort(Protocol):
    """Authenticated head of one committed profile-label lineage."""

    @property
    def label_revision(self) -> int:
        """The latest authenticated label revision."""
        ...

    @property
    def label_content_digest(self) -> str:
        """The content digest of the latest authenticated label."""
        ...

    @property
    def label_self_digest(self) -> str:
        """The self-digest of the latest authenticated label."""
        ...

    @property
    def self_digest(self) -> str:
        """The self-digest authenticating this lineage head."""
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

    @property
    def capsule_path(self) -> Path:
        """Where the recognized capsule this material was read from lives.

        The application does not open custody files by path; the provider owns
        those reads. The path identifies the exact recognized capsule.
        """
        ...

    @property
    def commit(self) -> ProfileCustodyCommitPort:
        """The capsule publication marker that authenticated this material."""
        ...


class ProfileCustodyPasswordProofMaterialPort(Protocol):
    """Only the two records a password proof reads."""

    @property
    def envelope(self) -> ProfileCustodyEnvelopePort:
        """The password envelope to unwrap."""
        ...

    @property
    def sentinel(self) -> ProfileCustodySentinelPort:
        """The sentinel that proves the unwrapped DEK."""
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

    def object_key_digest(self, object_key: str | bytes) -> bytes:
        """Derive the repository's stored lookup digest for one natural key."""
        ...

    def iter_all_records_raw(
        self,
        *,
        namespace: str | None = None,
    ) -> Iterator[ProfileCustodySecureObjectRawRowPort]:
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
        """Load and decrypt one object under its registered namespace contract.

        Core types:
        :class:`~cadrumo.core.classification.policies.SensitivityClass`.
        """
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

    def canonical_json_bytes(self) -> bytes:
        """Return the exact committed bytes of this envelope.

        Declared because a rotation must name the envelope it believes it is
        replacing: the compare-and-swap witness is the digest of these bytes,
        and computing it from anything else would let a concurrent write slip
        between the read and the swap. The application still reads no field of
        the payload -- it forwards the bytes and their digest, both opaque.
        """
        ...


class ProfileCustodySentinelPort(Protocol):
    """Opaque DEK-sentinel contract accepted by custody transactions."""

    profile_id: UUID

    def canonical_json_bytes(self) -> bytes:
        """Return the exact committed bytes of this sentinel.

        Declared for the same reason as the envelope's: a backup carries the
        record verbatim, and the archive is built from bytes rather than from
        fields. The bytes cross the boundary; their MEANING does not. Nothing
        here reads a field of the payload, and the sentinel carries no
        plaintext secret to read in any case.
        """
        ...


class ProfileCustodyRecoveryEnvelopePort(Protocol):
    """Recovery-envelope contract forwarded to custody storage.

    The two identity fields are declared because the application genuinely
    reads them: a recovery wrapper is only valid for the exact profile and
    DEK epoch it was minted against, and an enrollment that cannot be
    checked against the password envelope beside it is an enrollment nothing
    can prove belongs to this capsule. Everything else about the record --
    the KDF parameters, the wrapped key, the AAD descriptor -- stays opaque,
    because the application has no business INTERPRETING key material.

    "Interpreting" rather than "touching" is the precise line, and
    :meth:`canonical_json_bytes` is why it has to be stated. A backup carries
    this record verbatim, so the application does handle the whole of it --
    wrapped key, KDF parameters and all -- as an opaque run of bytes it
    forwards and digests without reading a field. What stays forbidden is
    deciding anything from the payload's contents. A reader who sees that
    method sitting under this paragraph should conclude the two agree, not
    that one of them is stale.
    """

    profile_id: UUID
    dek_epoch: str

    def canonical_json_bytes(self) -> bytes:
        """Return the exact committed bytes of this recovery wrapper."""
        ...


class ProfileCustodyLocalRecordStore(Protocol):
    """The filesystem capabilities needed by custody-owner authorities."""

    def ensure_directory(self, path: Path) -> None:
        """Create or validate one custody-owned directory."""
        ...

    def lock(self, path: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        """Return the anchored local-record lock context."""
        ...

    def root_lock(self, root: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        """Return the canonical profile-custody root lock context."""
        ...

    def read(self, path: Path, *, maximum_bytes: int) -> bytes:
        """Read one bounded, no-follow local record."""
        ...

    def write(self, path: Path, payload: bytes, *, publish_once: bool) -> None:
        """Atomically persist one local record."""
        ...

    def clear(self, path: Path) -> None:
        """Remove one anchored local record without following its leaf."""
        ...
