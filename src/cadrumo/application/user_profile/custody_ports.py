"""Typed application boundary for profile-custody infrastructure.

Application policy owns the neutral models and structural protocols declared
here. Persistence owns bucket layout, custody records, cryptography, key
material, and repository construction. An executable host binds that concrete
infrastructure for its lifetime through the single aggregate port below.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, NoReturn, Protocol, Self, cast, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...core import SecureObjectWrite, StorageCategory, storage_location
from ...core.classification import SensitivityClass
from ...core.errors import CoreError

if TYPE_CHECKING:
    from ...domain.buckets import BucketEventHistoryCatalogue
    from ...domain.user_profile.values import UserProfileSnapshot
    from .recovery_contracts import ProfileCustodyRecoveryArtifactWarning

from ...core.hashing import bounded_canonical_json_bytes, canonical_json_digest
from ...core.paths import effective_storage_root
from .authentication import ProfileAuthenticationRefusedError, ProfilePasswordProofOperation
from .login_session_port import profile_current_bucket_session, profile_session_serves_bucket


class ProfileCustodyCommitPort(Protocol):
    """Publication identity exposed by one recognized profile capsule."""

    @property
    def transaction_id(self) -> UUID:
        """The transaction that durably published this capsule."""
        ...

    @property
    def publication_kind(self) -> Literal["enroll", "restore"]:
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
        """Load and decrypt one object under its registered namespace contract."""
        ...

    def apply_batch(self, writes: tuple[SecureObjectWrite, ...]) -> None:
        """Commit an atomic set of encrypted-object writes."""
        ...


class ProfileSnapshotPersistencePort(Protocol):
    """Encrypted persistence boundary for immutable filing-time snapshots."""

    def exists(self, snapshot_id: str) -> bool:
        """Report whether one immutable snapshot row exists."""
        ...

    def load(self, snapshot_id: str) -> UserProfileSnapshot | None:
        """Load and decode one snapshot, or report its absence."""
        ...

    def save(self, snapshot: UserProfileSnapshot) -> None:
        """Encode and persist one immutable snapshot."""
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

    def read_optional(self, path: Path, *, maximum_bytes: int) -> bytes | None:
        """Read one bounded local record or prove its anchored absence."""
        ...

    def write(self, path: Path, payload: bytes, *, publish_once: bool) -> None:
        """Atomically persist one local record."""
        ...

    def clear(self, path: Path) -> None:
        """Remove one anchored local record without following its leaf."""
        ...

    def compare_and_replace(
        self,
        path: Path,
        *,
        expected: bytes | None,
        replacement: bytes,
        maximum_bytes: int,
    ) -> None:
        """CAS-replace one local record without a separate app-layer read."""
        ...

    def compare_and_replace_same_or_predecessor(
        self,
        path: Path,
        *,
        current: bytes,
        predecessor: bytes | None,
        maximum_bytes: int,
    ) -> None:
        """Idempotently CAS one local record without an app-layer read."""
        ...

    def compare_and_clear(self, path: Path, *, expected: bytes, maximum_bytes: int) -> None:
        """CAS-clear one local record without a separate app-layer read."""
        ...


def canonical_snapshot_payload(model: BaseModel) -> dict[str, object]:
    """Return a snapshot's canonical digest payload without its self-digest."""
    payload = cast(dict[str, object], model.model_dump(mode="json"))
    del payload["self_digest"]
    return payload


def canonical_snapshot_bytes(
    model: BaseModel,
    *,
    maximum_bytes: int,
    subject: str,
) -> bytes:
    """Encode one snapshot deterministically, enforcing its byte budget."""
    return bounded_canonical_json_bytes(
        model.model_dump(mode="json"),
        maximum_bytes=maximum_bytes,
        subject=subject,
    )


def canonical_snapshot_digest(
    model: BaseModel,
    *,
    maximum_bytes: int,
    subject: str,
) -> str:
    """Digest the canonical snapshot fields that exclude ``self_digest``."""
    return canonical_json_digest(
        canonical_snapshot_payload(model),
        maximum_bytes=maximum_bytes,
        subject=subject,
    )


def profile_custody_owner_root(root: Path | None, owner: str) -> Path:
    """Return one canonical owner directory below profile-custody evidence."""
    storage_root = effective_storage_root(root)
    return storage_root / storage_location(StorageCategory.PROFILE_CUSTODY_HOLD_EVIDENCE).relative_path() / owner


def ensure_profile_custody_owner_root(store: ProfileCustodyLocalRecordStore, root: Path) -> None:
    """Create the anchored evidence hierarchy needed by one custody owner."""
    for directory in (root.parent.parent, root.parent, root):
        store.ensure_directory(directory)


def default_profile_custody_local_record_store() -> ProfileCustodyLocalRecordStore:
    """Resolve the composed local-record store through the custody boundary."""
    return profile_custody_port().local_record_store()


class ProfileRecordCryptoError(CoreError, RuntimeError):
    """The configured profile-record crypto provider rejected an operation.

    Roots at :class:`~core.errors.CoreError` so the refusal binds to the error
    registry rather than reaching an operator as an unregistered builtin. The
    port deliberately does not root at the persistence layer's own
    :exc:`~adapters.persistence.storage.EncryptionError`: this package exists
    to keep the adapter's crypto types off the application port, and adopting
    that family would make the port's refusal catchable by every storage-family
    handler — a broadening, not a re-root. :exc:`RuntimeError` is retained so
    the ancestry every existing caller was written against is unchanged.
    """


class ProfileCustodyRecordIntegrityError(CoreError, ValueError):
    """The persistence provider refused a malformed or altered custody record."""


class ProfileRecordEncryptedBlob(BaseModel):
    """Neutral encrypted-record shape exchanged across the application port."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

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

    def open_with_passphrase(
        self,
        blob: ProfileRecordEncryptedBlob,
        *,
        passphrase: bytes,
        parameters: ProfilePassphraseKdfParameters,
        associated_data: bytes,
    ) -> bytes:
        """Derive the persisted passphrase key and authenticate one record."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileCustodyRegistrationMaterial:
    """The envelope and sentinel minted for one new profile."""

    envelope: ProfileCustodyEnvelopePort
    sentinel: ProfileCustodySentinelPort


@dataclass(frozen=True, slots=True)
class ProfileCustodyRecordSessionMaterial:
    """The exact envelope and DEK already authenticated for one profile."""

    envelope: ProfileCustodyEnvelopePort
    dek: bytes


@dataclass(frozen=True, slots=True)
class ProfileCustodyCapsuleSourceMaterial:
    """Parsed unpublished capsule members required by restore orchestration."""

    password_envelope: ProfileCustodyEnvelopePort
    sentinel: ProfileCustodySentinelPort
    database_bytes: bytes


@dataclass(frozen=True, slots=True)
class ProfileCapsuleArchiveHeaderMaterial:
    """Plaintext archive header fields observed by profile lifecycle policy."""

    product: str
    bucket_id: str
    manifest_digest: str
    archive_schema_version: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ProfileCapsuleArchiveContentsMaterial:
    """Opaque sealed-container result supplied to profile archive policy."""

    header: ProfileCapsuleArchiveHeaderMaterial
    payload_bytes: bytes


def profile_capsule_archive_schema_version() -> int:
    """Return the sealed-container schema version implemented by persistence."""
    return profile_custody_port().archive_schema_version()


def write_profile_capsule_archive_container(
    target: Path,
    *,
    header: ProfileCapsuleArchiveHeaderMaterial,
    payload_bytes: bytes,
) -> None:
    """Write an opaque profile payload through the sealed-container provider."""
    profile_custody_port().write_archive_container(
        target,
        header=header,
        payload_bytes=payload_bytes,
    )


def read_profile_capsule_archive_container(source: Path) -> ProfileCapsuleArchiveContentsMaterial:
    """Read an opaque profile payload through the sealed-container provider."""
    return profile_custody_port().read_archive_container(source)


def parse_profile_custody_capsule_members(
    *, envelope_bytes: bytes, sentinel_bytes: bytes, database_bytes: bytes
) -> ProfileCustodyCapsuleSourceMaterial:
    """Parse archive-carried custody records through their persistence owner."""
    return profile_custody_port().parse_capsule_members(
        envelope_bytes=envelope_bytes,
        sentinel_bytes=sentinel_bytes,
        database_bytes=database_bytes,
    )


def read_profile_custody_capsule_source(source: Path) -> ProfileCustodyCapsuleSourceMaterial:
    """Read and parse one unpublished capsule through the custody provider."""
    return profile_custody_port().read_capsule_source(source)


class ProfileRecoveryKeyPort(Protocol):
    """Wipeable recovery secret held across the enrollment handoff."""

    @property
    def mnemonic(self) -> str:
        """Return the exact 24-word recovery mnemonic."""
        ...

    def wipe(self) -> None:
        """Overwrite the key material owned by this container."""
        ...

    def __enter__(self) -> Self:
        """Retain the key until the caller's explicit handoff scope closes."""
        ...

    def __exit__(self, *_exc_info: object) -> None:
        """Wipe the key material when its handoff scope closes."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileCustodyRecoveryEnrollmentMaterial:
    """Creation-only recovery wrapper and the minted secret that opens it.

    The secret is handed back in its wipeable container rather than as a
    ``str``, because the operator holds it across an interactive
    confirmation and a string copy is unreachable by any wipe primitive for
    its whole lifetime. The caller owns the wipe.
    """

    envelope: ProfileCustodyRecoveryEnvelopePort
    recovery_key: ProfileRecoveryKeyPort


class ProfileCustodyUnlockPort(Protocol):
    """A current-envelope DEK accepted only after the sentinel proof."""

    @property
    def profile_id(self) -> UUID:
        """The profile whose envelope produced this key material."""
        ...

    @property
    def envelope_digest(self) -> str:
        """The digest of the exact envelope that was unwrapped."""
        ...

    @property
    def dek(self) -> bytes:
        """The authenticated data-encryption key."""
        ...


class ProfileCustodyRecoveryUnlockPort(Protocol):
    """A DEK accepted through the explicit recovery-artifact door."""

    @property
    def profile_id(self) -> UUID:
        """The profile whose recovery artifact produced this key."""
        ...

    @property
    def dek_epoch(self) -> str:
        """The DEK epoch bound into the proven artifact."""
        ...

    @property
    def recovery_digest(self) -> str:
        """The digest of the exact recovery record that was proved."""
        ...

    @property
    def dek(self) -> bytes:
        """The authenticated data-encryption key."""
        ...


class ProfileCustodyRecoveryArtifactPort(Protocol):
    """Non-secret artifact identity fields projected after export."""

    @property
    def profile_id(self) -> UUID:
        """The profile named by the artifact."""
        ...

    @property
    def dek_epoch(self) -> str:
        """The DEK epoch named by the artifact."""
        ...

    @property
    def self_digest(self) -> str:
        """The artifact's canonical self-digest."""
        ...


@runtime_checkable
class ProfileCustodyRecoveryArtifactExportReceiptPort(Protocol):
    """Durable artifact export result consumed by application policy."""

    @property
    def artifact(self) -> ProfileCustodyRecoveryArtifactPort:
        """The exported artifact's non-secret identity."""
        ...

    @property
    def target(self) -> Path:
        """The exact path durably created by the export."""
        ...

    @property
    def warnings(self) -> tuple[ProfileCustodyRecoveryArtifactWarning, ...]:
        """The mandatory operator warnings carried by every export."""
        ...


@dataclass(frozen=True, slots=True)
class ProfileCustodySecureObjectNamespace:
    """Registered namespace contract needed by an application capsule."""

    namespace: str
    sensitivity: SensitivityClass
    schema_version: int


class ProfileCustodyBucketEventHistoryPort(Protocol):
    """Current bucket-event history authority for custody-bound operations."""

    def exists(self) -> bool:
        """Return whether the encrypted event catalogue has been persisted."""
        ...

    def load(self) -> BucketEventHistoryCatalogue:
        """Load the current bucket event catalogue."""
        ...

    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        """Persist one complete event catalogue through the active secure store."""
        ...

    def load_revisioned(self) -> tuple[BucketEventHistoryCatalogue, str]:
        """Load the catalogue together with its secure-object CAS revision."""
        ...

    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        """Prepare an atomic secure-object write for the catalogue."""
        ...


class ProfileBucketStoragePathsPort(Protocol):
    """Resolved filesystem paths for one profile bucket."""

    @property
    def bucket_dir(self) -> Path:
        """The bucket's own directory."""
        ...

    @property
    def db_dir(self) -> Path:
        """The directory holding the bucket's database."""
        ...

    @property
    def blobs_dir(self) -> Path:
        """The directory holding the bucket's content-addressed blobs."""
        ...

    @property
    def database_file(self) -> Path:
        """The bucket's encrypted database file."""
        ...

    @property
    def bucket_id(self) -> str:
        """The bucket these paths were resolved for.

        Declared because the lock refusals name it, which is what lets this
        narrowed view satisfy the bucket lock's own target protocol directly.
        Without it the two lock delegations had to re-widen the port back to
        the concrete record through a runtime identity check -- a check that
        stood in for exactly this declaration.
        """
        ...


class ProfileBucketStoragePort(Protocol):
    """Bucket layout and lock operations exposed to application authorities."""

    def resolve(self, root: Path, bucket_id: str) -> ProfileBucketStoragePathsPort:
        """Resolve one bucket's paths without touching the filesystem."""
        ...

    def acquire_lock(self, paths: ProfileBucketStoragePathsPort, *, wait_seconds: float) -> None:
        """Acquire the canonical lock for a bucket target."""
        ...

    def release_lock(self, paths: ProfileBucketStoragePathsPort) -> None:
        """Release the canonical lock for a bucket target."""
        ...


class ProfileSecureObjectInventoryPort(Protocol):
    """Read-only namespace inventory for the authenticated active bucket."""

    def list_namespaces(self) -> tuple[str, ...]:
        """Return the registered namespaces present in the active bucket."""
        ...

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        """Return object keys present in one namespace."""
        ...


class ProfileCustodyInventoryEntryPort(Protocol):
    """One non-secret capsule member observed by physical custody storage."""

    @property
    def size_bytes(self) -> int: ...


class ProfileCustodyInventoryPort(Protocol):
    """Exact inventory shape consumed by application custody transactions."""

    @property
    def digest(self) -> str: ...

    @property
    def digest_entries(self) -> tuple[ProfileCustodyInventoryEntryPort, ...]: ...


class ProfileCustodyPort(Protocol):
    """Complete persistence capability required by profile-custody policy."""

    def local_record_store(self) -> ProfileCustodyLocalRecordStore:
        """Return the canonical anchored local-record store."""
        ...

    def archive_schema_version(self) -> int:
        """Return the current sealed-profile archive schema version."""
        ...

    def write_archive_container(
        self,
        target: Path,
        *,
        header: ProfileCapsuleArchiveHeaderMaterial,
        payload_bytes: bytes,
    ) -> None:
        """Write one opaque sealed profile archive."""
        ...

    def read_archive_container(self, source: Path) -> ProfileCapsuleArchiveContentsMaterial:
        """Read one opaque sealed profile archive."""
        ...

    def parse_capsule_members(
        self,
        *,
        envelope_bytes: bytes,
        sentinel_bytes: bytes,
        database_bytes: bytes,
    ) -> ProfileCustodyCapsuleSourceMaterial:
        """Parse archive-carried custody records through their owner."""
        ...

    def read_capsule_source(self, source: Path) -> ProfileCustodyCapsuleSourceMaterial:
        """Read and parse one unpublished capsule directory."""
        ...

    def inventory_committed(self, profile_id: UUID, *, root: Path | None = None) -> ProfileCustodyInventoryPort:
        """Observe the canonical committed-capsule inventory."""
        ...

    def create_capsule_label(self, *, profile_id: UUID, label: str) -> ProfileCustodyCapsuleLabelPort:
        """Create the canonical initial label record for a new capsule."""
        ...

    def staging_path(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        """Resolve the transaction-owned sibling staging path."""
        ...

    def deletion_path(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        """Resolve the transaction-owned deletion tombstone path."""
        ...

    def committed_capsule_path(self, profile_id: UUID, *, root: Path) -> Path | None:
        """Return the recognized current-format capsule path when committed."""
        ...

    def list_committed_profile_ids(self, *, root: Path) -> tuple[UUID, ...]:
        """List recognized current-format capsule identities."""
        ...

    def load_committed_capsule_label(self, profile_id: UUID, *, root: Path) -> ProfileCustodyCapsuleLabelPort:
        """Load the authenticated label from one committed capsule."""
        ...

    def verify_or_recover_initial_label_head(
        self,
        *,
        label: ProfileCustodyCapsuleLabelPort,
        source_witness: str,
        root: Path,
    ) -> ProfileCustodyLabelHeadPort:
        """Verify the label head or recover its initial committed witness."""
        ...

    def load_staged_capsule_label(
        self,
        profile_id: UUID,
        transaction_id: UUID,
        *,
        root: Path,
    ) -> ProfileCustodyCapsuleLabelPort:
        """Load the authenticated label from one transaction-owned stage."""
        ...

    def stage_capsule(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        publication_kind: Literal["enroll", "restore"],
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        data_files: Mapping[str, bytes],
        label_record: ProfileCustodyCapsuleLabelPort,
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None,
        root: Path,
        published_at: datetime,
        stage_initializer: Callable[[Path], None] | None,
    ) -> Path:
        """Durably build, but do not publish, one transaction-owned capsule stage."""
        ...

    def inventory_staged(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        root: Path,
    ) -> ProfileCustodyInventoryPort:
        """Observe the exact inventory of one transaction-owned stage."""
        ...

    def publish_staged(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        """Atomically publish one verified transaction-owned stage."""
        ...

    def write_deletion_marker(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        inventory_digest: str,
        root: Path,
    ) -> None:
        """Bind one prepared deletion to its committed capsule."""
        ...

    def verify_deletion_marker(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        inventory_digest: str,
        root: Path,
    ) -> None:
        """Authenticate the prepared marker while its capsule remains current."""
        ...

    def verify_deletion_tombstone(
        self,
        *,
        profile_id: UUID,
        transaction_id: UUID,
        inventory_digest: str,
        root: Path,
    ) -> None:
        """Authenticate the exact renamed capsule before local removal."""
        ...

    def rename_capsule_for_deletion(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> Path:
        """Atomically rename one marked capsule to its transaction tombstone."""
        ...

    def remove_deletion_tombstone(self, *, profile_id: UUID, transaction_id: UUID, root: Path) -> None:
        """Remove only the transaction-owned, previously verified tombstone."""
        ...

    def bucket_storage(self) -> ProfileBucketStoragePort:
        """Return canonical bucket path and lock operations."""
        ...

    def read_output_language_hint(self, *, storage_root: Path, bucket_id: str) -> str | None:
        """Read one bucket's non-secret failure-rendering language hint."""
        ...

    def secure_object_inventory(self) -> ProfileSecureObjectInventoryPort:
        """Return active-bucket namespace inventory."""
        ...

    def profile_snapshot_persistence(
        self,
        bucket_id: str,
        *,
        object_key: Callable[[str, str], str],
        objects: ProfileCustodySecureObjectRepositoryPort | None = None,
    ) -> ProfileSnapshotPersistencePort:
        """Return immutable profile-snapshot persistence for one bucket."""
        ...

    def record_crypto(self) -> ProfileRecordCryptoPort:
        """Return the profile-record AEAD adapter."""
        ...

    def create_registration_material(
        self,
        *,
        profile_id: UUID,
        password: str,
        dek: bytes,
        dek_epoch: str,
        salt: bytes,
        password_generation: int,
    ) -> ProfileCustodyRegistrationMaterial:
        """Mint a password envelope and its DEK sentinel."""
        ...

    def create_recovery_enrollment_material(
        self,
        *,
        profile_id: UUID,
        dek: bytes,
        dek_epoch: str,
        salt: bytes,
    ) -> ProfileCustodyRecoveryEnrollmentMaterial:
        """Mint a recovery wrapper and its wipeable secret."""
        ...

    def export_recovery_artifact(
        self,
        recovery_envelope: ProfileCustodyRecoveryEnvelopePort,
        *,
        current_password: str,
        password_envelope: ProfileCustodyEnvelopePort,
        sentinel: ProfileCustodySentinelPort,
        target: Path,
    ) -> ProfileCustodyRecoveryArtifactExportReceiptPort:
        """Prove and durably export one portable recovery artifact."""
        ...

    def prove_recovery_artifact(
        self,
        source: Path,
        *,
        recovery_secret: str,
        expected_profile_id: UUID,
        expected_dek_epoch: str,
        sentinel: ProfileCustodySentinelPort,
    ) -> ProfileCustodyRecoveryUnlockPort:
        """Read and prove one named recovery artifact."""
        ...

    def verify_dek_against_sentinel(
        self,
        *,
        dek: bytes,
        profile_id: UUID,
        dek_epoch: str,
        sentinel: ProfileCustodySentinelPort,
    ) -> None:
        """Prove that a DEK opens the exact profile sentinel."""
        ...

    def recovery_envelope_path(self, capsule_path: Path) -> Path:
        """Return the current-format recovery-envelope path."""
        ...

    def unlock_password(
        self,
        material: ProfileCustodyPasswordProofMaterialPort,
        *,
        password: str,
    ) -> ProfileCustodyUnlockPort:
        """Authenticate one committed password envelope and sentinel."""
        ...

    def replace_password_envelope(
        self,
        *,
        profile_id: UUID,
        current: ProfileCustodyEnvelopePort,
        rotated: ProfileCustodyEnvelopePort,
        root: Path,
    ) -> None:
        """CAS-replace exactly one committed password envelope."""
        ...

    def load_password_material(
        self,
        profile_id: UUID,
        *,
        root: Path | None = None,
    ) -> ProfileCustodyPasswordMaterialPort:
        """Load the committed password proof material for one profile."""
        ...

    def is_authentication_proof_failure(
        self,
        error: BaseException,
        *,
        operation: ProfilePasswordProofOperation,
    ) -> bool:
        """Recognise a password or recovery proof refusal."""
        ...

    def refuse_login_without_password_channel(self) -> NoReturn:
        """Raise the canonical refusal for an absent password channel."""
        ...

    def is_authentication_failure(self, error: BaseException) -> bool:
        """Recognise a key-provider authentication failure."""
        ...

    def is_keyring_unavailable(self, error: BaseException) -> bool:
        """Recognise an unavailable keychain provider."""
        ...

    def is_persistence_failure(self, error: BaseException) -> bool:
        """Recognise a governed persistence failure without leaking adapter types."""
        ...

    def secure_object_namespace(self) -> ProfileCustodySecureObjectNamespace:
        """Return the registered current-profile value namespace."""
        ...

    def secure_object_repository(
        self,
        *,
        profile_id: UUID,
        dek: bytes,
        root: Path,
        database_file: Path | None = None,
    ) -> AbstractContextManager[ProfileCustodySecureObjectRepositoryPort]:
        """Open the canonical encrypted-object repository for one capsule."""
        ...

    def bucket_event_history_repository(
        self,
        *,
        objects: ProfileCustodySecureObjectRepositoryPort | None = None,
    ) -> ProfileCustodyBucketEventHistoryPort:
        """Return the canonical encrypted bucket-event repository."""
        ...


_BOUND_PROFILE_CUSTODY_PORT: ContextVar[ProfileCustodyPort] = ContextVar("cadrumo_profile_custody_port")


@contextmanager
def bind_profile_custody_port(port: ProfileCustodyPort) -> Generator[ProfileCustodyPort]:
    """Bind one outward-composed custody port for the host execution context."""
    token = _BOUND_PROFILE_CUSTODY_PORT.set(port)
    try:
        yield port
    finally:
        _BOUND_PROFILE_CUSTODY_PORT.reset(token)


def profile_custody_port() -> ProfileCustodyPort:
    """Resolve the explicitly composed custody port for the current host."""
    try:
        return _BOUND_PROFILE_CUSTODY_PORT.get()
    except LookupError as error:
        raise RuntimeError("profile custody infrastructure has not been composed") from error


def inventory_committed_profile_custody(profile_id: UUID, *, root: Path | None = None) -> ProfileCustodyInventoryPort:
    """Observe one committed capsule through the custody persistence boundary."""
    return profile_custody_port().inventory_committed(profile_id, root=root)


def default_profile_bucket_storage() -> ProfileBucketStoragePort:
    """Return canonical bucket layout and locking through the application port."""
    return profile_custody_port().bucket_storage()


def read_profile_output_language_hint(*, storage_root: Path, bucket_id: str) -> str | None:
    """Read one bucket's non-secret output-language hint through custody."""
    return profile_custody_port().read_output_language_hint(
        storage_root=storage_root,
        bucket_id=bucket_id,
    )


def default_profile_secure_object_inventory() -> ProfileSecureObjectInventoryPort:
    """Return active-bucket namespace inventory through the application port."""
    return profile_custody_port().secure_object_inventory()


def default_profile_record_crypto_port() -> ProfileRecordCryptoPort:
    """Return the production crypto adapter through the application port."""
    return profile_custody_port().record_crypto()


def create_profile_custody_registration_material(
    *,
    profile_id: UUID,
    password: str,
    dek: bytes,
    dek_epoch: str,
    salt: bytes,
    password_generation: int = 1,
) -> ProfileCustodyRegistrationMaterial:
    """Mint the password envelope and DEK sentinel at the custody boundary.

    ``password_generation`` defaults to the first, which is what creation
    wants. A rotation passes the successor: the same DEK and the same epoch
    re-wrapped under a new password, which is why this mint serves both doors
    instead of a rotation growing a parallel one.
    """
    return profile_custody_port().create_registration_material(
        profile_id=profile_id,
        password=password,
        dek=dek,
        dek_epoch=dek_epoch,
        salt=salt,
        password_generation=password_generation,
    )


"""Recovery-artifact warnings remain a closed value set for exhaustive rendering.

Passing their defining type through the custody port prevents operator surfaces
from flattening an exhaustively handled warning into an unchecked string.
"""


def create_profile_recovery_enrollment_material(
    *,
    profile_id: UUID,
    dek: bytes,
    dek_epoch: str,
    salt: bytes,
) -> ProfileCustodyRecoveryEnrollmentMaterial:
    """Mint the mandatory creation wrapper and its secret at the custody boundary.

    The secret is a 24-word BIP-39 mnemonic over 256 bits of entropy rather
    than an operator-typed string. That choice is what makes the wrapper
    safe to export: an exported artifact's only remaining barrier is the KDF
    cost applied to whatever entropy the secret carries, and a human-chosen
    string does not survive offline guessing at any cost this machine can
    afford to spend on every login.

    The recovery wrapper is calibrated against its OWN salt, independent of
    the password envelope's. The two wrappers cover the same DEK through
    genuinely independent derivations, so compromising one KDF input cannot
    shorten an attack on the other.
    """
    return profile_custody_port().create_recovery_enrollment_material(
        profile_id=profile_id,
        dek=dek,
        dek_epoch=dek_epoch,
        salt=salt,
    )


def export_profile_recovery_artifact(
    recovery_envelope: ProfileCustodyRecoveryEnvelopePort,
    *,
    current_password: str,
    password_envelope: ProfileCustodyEnvelopePort,
    sentinel: ProfileCustodySentinelPort,
    target: Path,
) -> ProfileCustodyRecoveryArtifactExportReceiptPort:
    """Write one durable external recovery artifact through the custody owner.

    The destination guard, the current-password proof, and the exclusive
    create all live in the custody module that owns the artifact format;
    this boundary only narrows the application's ports back to the
    substrate records that module requires.
    """
    return profile_custody_port().export_recovery_artifact(
        recovery_envelope,
        current_password=current_password,
        password_envelope=password_envelope,
        sentinel=sentinel,
        target=target,
    )


def prove_profile_recovery_artifact(
    source: Path,
    *,
    recovery_secret: str,
    expected_profile_id: UUID,
    expected_dek_epoch: str,
    sentinel: ProfileCustodySentinelPort,
) -> ProfileCustodyRecoveryUnlockPort:
    """Read one artifact and prove it against its named identity and sentinel.

    Import and unlock are kept as one boundary call because a parsed but
    unproven artifact is not a useful application value: it carries an
    identity claim nothing has checked. Both halves refuse an artifact whose
    UUID or DEK epoch differs from the target named here, so a substituted
    artifact is refused twice before any key material exists.

    This installs nothing. Proving an artifact does not enroll it, does not
    overwrite committed recovery, and does not change any key schedule.
    """
    return profile_custody_port().prove_recovery_artifact(
        source,
        recovery_secret=recovery_secret,
        expected_profile_id=expected_profile_id,
        expected_dek_epoch=expected_dek_epoch,
        sentinel=sentinel,
    )


def verify_profile_custody_dek_against_sentinel(
    *,
    dek: bytes,
    profile_id: UUID,
    dek_epoch: str,
    sentinel: ProfileCustodySentinelPort,
) -> None:
    """Prove a key opens this exact profile before anything is published."""
    profile_custody_port().verify_dek_against_sentinel(
        dek=dek,
        profile_id=profile_id,
        dek_epoch=dek_epoch,
        sentinel=sentinel,
    )


#: Per-member capsule-directory ceilings are declared by the custody port so
#: restore uses the same bounds as the published capsule reader.


def profile_custody_recovery_envelope_path(capsule_path: Path) -> Path:
    """Return where a creation-published capsule keeps its recovery wrapper."""
    return profile_custody_port().recovery_envelope_path(capsule_path)


def unlock_profile_custody_password(
    material: ProfileCustodyPasswordProofMaterialPort,
    *,
    password: str,
) -> ProfileCustodyUnlockPort:
    """Authenticate one committed profile through its password envelope.

    This is the normal-login authority: the adapter runs the bounded
    supervised KDF and proves the resulting DEK against the committed
    sentinel before it returns any key material.  It intentionally accepts
    material already loaded from the exact target capsule, so a caller cannot
    resolve one profile and unwrap another through ambient state.
    """
    return profile_custody_port().unlock_password(material, password=password)


def replace_profile_custody_password_envelope(
    *,
    profile_id: UUID,
    current: ProfileCustodyEnvelopePort,
    rotated: ProfileCustodyEnvelopePort,
    root: Path,
) -> None:
    """CAS-replace exactly one committed password envelope through its owner."""
    profile_custody_port().replace_password_envelope(
        profile_id=profile_id,
        current=current,
        rotated=rotated,
        root=root,
    )


def load_profile_custody_password_material(
    profile_id: UUID, *, root: Path | None = None
) -> ProfileCustodyPasswordMaterialPort:
    """Load committed password proof material through the custody boundary."""
    return profile_custody_port().load_password_material(profile_id, root=root)


def map_profile_authentication_proof_failure(
    error: BaseException,
    *,
    operation: ProfilePasswordProofOperation,
) -> ProfileAuthenticationRefusedError | None:
    """Collapse credential shape and proof failures for one named capability."""
    if not profile_custody_port().is_authentication_proof_failure(error, operation=operation):
        return None
    return ProfileAuthenticationRefusedError()


def refuse_profile_login_without_password_channel() -> NoReturn:
    """Raise the current custody refusal for an absent explicit password channel."""
    profile_custody_port().refuse_login_without_password_channel()


def profile_custody_record_session_material(
    profile_id: UUID,
    *,
    root: Path | None = None,
) -> ProfileCustodyRecordSessionMaterial | None:
    """Return record material only when the live session serves this profile."""
    session = profile_current_bucket_session()
    if session is None or not profile_session_serves_bucket(session, str(profile_id)):
        return None
    material = load_profile_custody_password_material(profile_id, root=root)
    return ProfileCustodyRecordSessionMaterial(envelope=material.envelope, dek=session.dek)


def profile_is_authentication_failure(error: BaseException) -> bool:
    """Recognise the typed authentication refusals without leaking adapter types."""
    return profile_custody_port().is_authentication_failure(error)


def profile_is_keyring_unavailable(error: BaseException) -> bool:
    """Recognise a keychain persistence refusal for the process-scoped fallback."""
    return profile_custody_port().is_keyring_unavailable(error)


def profile_is_persistence_failure(error: BaseException) -> bool:
    """Recognise the storage failure family through the composed custody port."""
    return profile_custody_port().is_persistence_failure(error)


def profile_custody_secure_object_namespace() -> ProfileCustodySecureObjectNamespace:
    """Resolve the registered current-profile value namespace at the app boundary."""
    return profile_custody_port().secure_object_namespace()


def profile_custody_secure_object_repository(
    *,
    profile_id: UUID,
    dek: bytes,
    root: Path,
    database_file: Path | None = None,
) -> AbstractContextManager[ProfileCustodySecureObjectRepositoryPort]:
    """Open the canonical encrypted-object repository for one profile capsule.

    The provider owns the persistence/runtime imports and the short-lived
    staging session needed before a capsule has been published. Application
    authorities consume only this narrow repository port.
    """
    return profile_custody_port().secure_object_repository(
        profile_id=profile_id,
        dek=dek,
        root=root,
        database_file=database_file,
    )


def default_profile_bucket_event_history_repository(
    *,
    objects: ProfileCustodySecureObjectRepositoryPort | None = None,
) -> ProfileCustodyBucketEventHistoryPort:
    """Resolve the encrypted bucket-event repository at the app boundary."""
    return profile_custody_port().bucket_event_history_repository(objects=objects)


__all__ = [
    "ProfileBucketStoragePathsPort",
    "ProfileBucketStoragePort",
    "ProfileCustodyBucketEventHistoryPort",
    "ProfileCustodyCapsuleLabelPort",
    "ProfileCustodyCommitPort",
    "ProfileCustodyEnvelopePort",
    "ProfileCustodyLabelHeadPort",
    "ProfileCustodyLocalRecordStore",
    "ProfileCustodyPasswordMaterialPort",
    "ProfileCustodyPasswordProofMaterialPort",
    "ProfileCustodyPort",
    "ProfileCustodyRecordIntegrityError",
    "ProfileCustodyRecordSessionMaterial",
    "ProfileCustodyRecoveryArtifactExportReceiptPort",
    "ProfileCustodyRecoveryArtifactPort",
    "ProfileCustodyRecoveryEnrollmentMaterial",
    "ProfileCustodyRecoveryEnvelopePort",
    "ProfileCustodyRecoveryUnlockPort",
    "ProfileCustodyRegistrationMaterial",
    "ProfileCustodySecureObjectNamespace",
    "ProfileCustodySecureObjectRawRowPort",
    "ProfileCustodySecureObjectRecordPort",
    "ProfileCustodySecureObjectRepositoryPort",
    "ProfileCustodySentinelPort",
    "ProfileCustodyUnlockPort",
    "ProfilePassphraseEncryptedRecord",
    "ProfilePassphraseKdfParameters",
    "ProfilePassphraseKdfPolicy",
    "ProfileRecordCryptoError",
    "ProfileRecordCryptoPort",
    "ProfileRecordEncryptedBlob",
    "ProfileRecoveryKeyPort",
    "ProfileSecureObjectInventoryPort",
    "ProfileSnapshotPersistencePort",
    "bind_profile_custody_port",
    "canonical_snapshot_bytes",
    "canonical_snapshot_digest",
    "canonical_snapshot_payload",
    "create_profile_custody_registration_material",
    "create_profile_recovery_enrollment_material",
    "default_profile_bucket_event_history_repository",
    "default_profile_bucket_storage",
    "default_profile_custody_local_record_store",
    "default_profile_record_crypto_port",
    "default_profile_secure_object_inventory",
    "ensure_profile_custody_owner_root",
    "export_profile_recovery_artifact",
    "map_profile_authentication_proof_failure",
    "profile_custody_owner_root",
    "profile_custody_port",
    "profile_custody_record_session_material",
    "profile_custody_recovery_envelope_path",
    "profile_custody_secure_object_namespace",
    "profile_custody_secure_object_repository",
    "profile_is_authentication_failure",
    "profile_is_keyring_unavailable",
    "profile_is_persistence_failure",
    "prove_profile_recovery_artifact",
    "read_profile_output_language_hint",
    "refuse_profile_login_without_password_channel",
    "replace_profile_custody_password_envelope",
    "unlock_profile_custody_password",
    "verify_profile_custody_dek_against_sentinel",
]
