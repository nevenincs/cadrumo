"""Application ports for custody records supplied to profile lifecycle actions.

The protocol declarations live beside the boundary helpers that bind them to
the real persistence facade: a consumer takes a narrowed port from here and
the default provider that satisfies it resolves from the same module, so the
custody surface has exactly one application-owned door.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, Protocol, TypeGuard, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import (
    USER_PROFILE_VALUE_NAMESPACE,
    KeyringUnavailableError,
    MasterKeyMaterialMissingError,
    SecureObjectRepository,
    bucket,
    crypto,
    generate_recovery_key,
    master_key,
    secure_object_repository_for_active_bucket,
    secure_object_repository_for_bucket,
    secure_object_repository_for_staged_bucket,
)
from ...core import SecureObjectWrite, StorageCategory, storage_location
from ...core.classification import SensitivityClass
from ...core.config import Settings
from ...core.errors import CoreError

if TYPE_CHECKING:
    from ...adapters.persistence.storage import RecoveryKey
    from ...domain.buckets import BucketEventHistoryCatalogue


from ...adapters.persistence.storage import custody
from ...core.hashing import bounded_canonical_json_bytes, canonical_json_digest
from ...core.paths import effective_storage_root

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

    @property
    def sealed(self) -> bool:
        """Whether this session has been closed and its key material zeroised.

        Closing zeroises the buffers in place rather than replacing the object,
        so a holder of a closed session sees something that still names its
        bucket and still answers every other question truthfully. Without this
        predicate the application layer could not ask whether a session it
        holds is spent, and had to infer it from a failure at the point of use
        -- which is how a retired session came to look identical to a live one
        to anything deciding whether to keep trusting it.
        """
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

    @property
    def capsule_path(self) -> Path:
        """Where the recognized capsule this material was read from lives.

        The application does not open custody files by path -- the provider
        owns that -- but it does need to ask whether an OPTIONAL member is
        present, and the recovery wrapper is the one member whose absence is a
        legitimate state rather than a fault. Recomputing the location here
        instead would be a second answer to where a capsule lives.
        """
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


def _substrate_handle[T](value: object, expected: type[T], subject: str) -> T:
    """Re-widen a narrowed custody handle to the substrate type that minted it.

    The record-shaped ports above narrow what the application may READ.  A few
    of the delegates below then hand the same object straight back to the
    substrate, which requires its own concrete type, and a narrowed view is not
    that type.  The reconciliation is a real check rather than an assertion:
    each of these handles is opaque to the application, so an object that did
    not come from the substrate is a composition error and custody refuses it
    instead of forwarding it.
    """
    if not isinstance(value, expected):
        raise TypeError(f"{subject} did not originate from the custody substrate: {type(value).__name__}")
    return value


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


class _PersistenceProfileCustodyLocalRecordStore:
    """Adapt the real persistence facade to the application-owned port."""

    def ensure_directory(self, path: Path) -> None:
        custody.ensure_profile_custody_local_directory(path)

    def lock(self, path: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        return custody.profile_custody_local_lock(path, timeout_seconds=timeout_seconds)

    def read(self, path: Path, *, maximum_bytes: int) -> bytes:
        return custody.read_profile_custody_local_record(path, maximum_bytes=maximum_bytes)

    def read_optional(self, path: Path, *, maximum_bytes: int) -> bytes | None:
        return custody.read_optional_profile_custody_local_record(path, maximum_bytes=maximum_bytes)

    def write(self, path: Path, payload: bytes, *, publish_once: bool) -> None:
        custody.write_profile_custody_local_record(path, payload, publish_once=publish_once)

    def clear(self, path: Path) -> None:
        custody.clear_profile_custody_local_record(path)

    def compare_and_replace(
        self,
        path: Path,
        *,
        expected: bytes | None,
        replacement: bytes,
        maximum_bytes: int,
    ) -> None:
        custody.compare_and_replace_profile_custody_local_record(
            path,
            expected=expected,
            replacement=replacement,
            maximum_bytes=maximum_bytes,
        )

    def compare_and_clear(self, path: Path, *, expected: bytes, maximum_bytes: int) -> None:
        custody.compare_and_clear_profile_custody_local_record(path, expected=expected, maximum_bytes=maximum_bytes)

    def compare_and_replace_same_or_predecessor(
        self,
        path: Path,
        *,
        current: bytes,
        predecessor: bytes | None,
        maximum_bytes: int,
    ) -> None:
        custody.compare_and_replace_same_or_predecessor_profile_custody_local_record(
            path,
            current=current,
            predecessor=predecessor,
            maximum_bytes=maximum_bytes,
        )


def default_profile_custody_local_record_store() -> ProfileCustodyLocalRecordStore:
    """Return the production custody adapter through the application boundary."""
    return _PersistenceProfileCustodyLocalRecordStore()


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


class ProfileRecordCryptoPort(Protocol):
    """AEAD operations required by the capsule record authority."""

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
class ProfileCustodyRecoveryEnrollmentMaterial:
    """One optional recovery wrapper and the minted secret that opens it.

    The secret is handed back in its wipeable container rather than as a
    ``str``, because the operator holds it across an interactive
    confirmation and a string copy is unreachable by any wipe primitive for
    its whole lifetime. The caller owns the wipe.
    """

    envelope: ProfileCustodyRecoveryEnvelopePort
    recovery_key: RecoveryKey


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


class ProfileLoginThrottleEvaluationPort(Protocol):
    """Failed-login backoff decision exposed to the application."""

    @property
    def throttled(self) -> bool:
        """Whether the caller must wait before another attempt."""
        ...

    @property
    def remaining_seconds(self) -> int:
        """Seconds left on the current backoff window."""
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


def committed_profile_custody_inventory(
    profile_id: UUID,
    *,
    root: Path | None = None,
) -> custody.ProfileCustodyInventory:
    """Return the exact bounded inventory of one profile's committed capsule.

    The application-owned door onto the capsule content fold, so a service that
    needs a capsule's exact digest, file count and byte total gets it from this
    port rather than importing the persistence adapter. The inventory follows no
    link and opens no encrypted payload; it observes file identity and size
    only, which is what makes it usable against a capsule nobody has unlocked.

    Raises:
        Exception: Whatever the custody adapter raises when the capsule is not
            committed or cannot be walked. Deliberately not narrowed here: a
            deletion caller must treat every failure as unassessable rather
            than substitute a fingerprint it did not observe.
    """
    return custody.inventory_committed_profile_custody_capsule(profile_id, root=root)


class _PersistenceProfileBucketStorage:
    """Adapt canonical bucket layout and locking to the application port."""

    def resolve(self, root: Path, bucket_id: str) -> ProfileBucketStoragePathsPort:
        return bucket.bucket_paths(root, bucket_id)

    def acquire_lock(self, paths: ProfileBucketStoragePathsPort, *, wait_seconds: float) -> None:
        bucket.acquire_lock(paths, wait_seconds=wait_seconds)

    def release_lock(self, paths: ProfileBucketStoragePathsPort) -> None:
        bucket.release_lock(paths)


class _PersistenceProfileSecureObjectInventory:
    """Adapt the active runtime repository to the inventory port."""

    def __init__(self) -> None:
        repository = secure_object_repository_for_active_bucket()
        self._list_namespaces = repository.list_namespaces
        self._list_keys = repository.list_keys

    def list_namespaces(self) -> tuple[str, ...]:
        return self._list_namespaces()

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        return self._list_keys(namespace)


class _PersistenceProfileRecordCrypto:
    """Adapt the real persistence crypto facade to the application port."""

    def encrypt_record(
        self,
        plaintext: bytes,
        *,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> ProfileRecordEncryptedBlob:
        try:
            blob = crypto.encrypt_record(plaintext, key=key, associated_data=associated_data)
            return ProfileRecordEncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext)
        except Exception as exc:
            raise ProfileRecordCryptoError("profile record encryption failed") from exc

    def decrypt_record(
        self,
        blob: ProfileRecordEncryptedBlob,
        *,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        try:
            adapter_blob = crypto.EncryptedBlob(nonce=blob.nonce, ciphertext=blob.ciphertext)
            return crypto.decrypt_record(adapter_blob, key=key, associated_data=associated_data)
        except Exception as exc:
            raise ProfileRecordCryptoError("profile record decryption failed") from exc


def default_profile_bucket_storage() -> ProfileBucketStoragePort:
    """Return canonical bucket layout and locking through the application port."""
    return _PersistenceProfileBucketStorage()


def default_profile_secure_object_inventory() -> ProfileSecureObjectInventoryPort:
    """Return active-bucket namespace inventory through the application port."""
    return _PersistenceProfileSecureObjectInventory()


def default_profile_record_crypto_port() -> ProfileRecordCryptoPort:
    """Return the production crypto adapter through the application port."""
    return _PersistenceProfileRecordCrypto()


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
    calibration = custody.calibrate_profile_kdf(salt=salt)
    envelope = custody.create_profile_custody_password_envelope(
        profile_id=profile_id,
        password=password,
        dek=dek,
        dek_epoch=dek_epoch,
        kdf=calibration.parameters,
        password_generation=password_generation,
    )
    sentinel = custody.create_profile_custody_sentinel(envelope=envelope, dek=dek)
    return ProfileCustodyRegistrationMaterial(envelope=envelope, sentinel=sentinel)


ProfileRecoveryArtifactWarning = custody.ProfileCustodyRecoveryArtifactWarning
"""The closed set of warnings every recovery-artifact export must surface.

Re-exported at the boundary rather than flattened to plain strings on the
way through. The warnings are a closed value set an operator surface has to
render exhaustively, and a surface that receives them as bare strings cannot
be checked for having handled all of them.
"""


def create_profile_recovery_enrollment_material(
    *,
    profile_id: UUID,
    dek: bytes,
    dek_epoch: str,
    salt: bytes,
) -> ProfileCustodyRecoveryEnrollmentMaterial:
    """Mint the optional recovery wrapper and its secret at the custody boundary.

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
    calibration = custody.calibrate_profile_kdf(salt=salt)
    recovery_key = generate_recovery_key()
    try:
        envelope = custody.create_profile_custody_recovery_envelope(
            profile_id=profile_id,
            recovery_secret=recovery_key.mnemonic,
            dek=dek,
            dek_epoch=dek_epoch,
            kdf=calibration.parameters,
        )
    except BaseException:
        recovery_key.wipe()
        raise
    return ProfileCustodyRecoveryEnrollmentMaterial(envelope=envelope, recovery_key=recovery_key)


def export_profile_recovery_artifact(
    recovery_envelope: ProfileCustodyRecoveryEnvelopePort,
    *,
    current_password: str,
    password_envelope: ProfileCustodyEnvelopePort,
    sentinel: ProfileCustodySentinelPort,
    target: Path,
) -> custody.ProfileCustodyRecoveryArtifactExportReceipt:
    """Write one durable external recovery artifact through the custody owner.

    The destination guard, the current-password proof, and the exclusive
    create all live in the custody module that owns the artifact format;
    this boundary only narrows the application's ports back to the
    substrate records that module requires.
    """
    return custody.export_profile_custody_recovery_artifact(
        _substrate_handle(recovery_envelope, custody.ProfileCustodyRecoveryEnvelope, "recovery envelope"),
        current_password=current_password,
        password_envelope=_substrate_handle(password_envelope, custody.ProfileCustodyEnvelope, "password envelope"),
        sentinel=_substrate_handle(sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel"),
        target=target,
    )


def prove_profile_recovery_artifact(
    source: Path,
    *,
    recovery_secret: str,
    expected_profile_id: UUID,
    expected_dek_epoch: str,
    sentinel: ProfileCustodySentinelPort,
) -> custody.ProfileCustodyRecoveryUnlock:
    """Read one artifact and prove it against its named identity and sentinel.

    Import and unlock are kept as one boundary call because a parsed but
    unproven artifact is not a useful application value: it carries an
    identity claim nothing has checked. Both halves refuse an artifact whose
    UUID or DEK epoch differs from the target named here, so a substituted
    artifact is refused twice before any key material exists.

    This installs nothing. Proving an artifact does not enroll it, does not
    overwrite committed recovery, and does not change any key schedule.
    """
    substrate_sentinel = _substrate_handle(sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel")
    artifact = custody.import_profile_custody_recovery_artifact(
        source,
        expected_profile_id=expected_profile_id,
        expected_dek_epoch=expected_dek_epoch,
    )
    return custody.unlock_imported_profile_custody_recovery_artifact(
        artifact,
        recovery_secret,
        sentinel=substrate_sentinel,
        expected_profile_id=expected_profile_id,
        expected_dek_epoch=expected_dek_epoch,
    )


def verify_profile_custody_dek_against_sentinel(
    *,
    dek: bytes,
    profile_id: UUID,
    dek_epoch: str,
    sentinel: ProfileCustodySentinelPort,
) -> None:
    """Prove a key opens this exact profile before anything is published."""
    custody.verify_profile_custody_sentinel(
        dek=dek,
        profile_id=profile_id,
        dek_epoch=dek_epoch,
        sentinel=_substrate_handle(sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel"),
    )


def load_profile_custody_password_material(
    profile_id: UUID,
    *,
    root: Path | None = None,
) -> ProfileCustodyPasswordMaterialPort:
    """Load the normal-password envelope through the custody provider."""
    return custody.load_committed_profile_password_material(profile_id, root=root)


def replace_profile_custody_envelope(
    profile_id: UUID,
    payload: bytes,
    *,
    expected_sha256: str,
    root: Path | None = None,
) -> None:
    """CAS-replace one committed capsule's password envelope.

    The application layer holds the transaction lock and supplies the digest
    of the envelope it believes it is replacing; the provider owns the
    filesystem discipline and refuses a payload that would change the DEK
    epoch or name another profile. Re-wrapping is the only sanctioned edit to
    a committed envelope -- there is no path here that re-keys one.
    """
    custody.replace_committed_profile_custody_envelope(
        profile_id,
        payload,
        expected_sha256=expected_sha256,
        root=root,
    )


def parse_profile_custody_envelope(payload: bytes) -> ProfileCustodyEnvelopePort:
    """Parse one canonical password envelope from bytes the caller holds.

    The committed-capsule reader cannot serve a restore, whose capsule is by
    definition unpublished, so its material arrives as bytes and is parsed
    here through the same strict record the publisher wrote. Parsing rather
    than trusting is the point: a torn member is refused before anything is
    republished, not discovered as a decryption failure afterwards.
    """
    return custody.parse_profile_custody_envelope(payload)


def parse_profile_custody_sentinel(payload: bytes) -> ProfileCustodySentinelPort:
    """Parse one canonical DEK sentinel from bytes the caller holds."""
    return custody.parse_profile_custody_sentinel_record(payload)


def parse_profile_custody_recovery_envelope(payload: bytes) -> ProfileCustodyRecoveryEnvelopePort:
    """Parse one canonical optional recovery wrapper from bytes the caller holds."""
    return custody.parse_profile_custody_recovery_envelope(payload)


def profile_custody_recovery_envelope_path(capsule_path: Path) -> Path:
    """Return where a committed capsule keeps its optional recovery wrapper."""
    return capsule_path / "custody" / custody.PROFILE_CUSTODY_RECOVERY_FILENAME


def unlock_profile_custody_password(
    material: ProfileCustodyPasswordMaterialPort,
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
    return custody.unlock_profile_custody(
        _substrate_handle(material.envelope, custody.ProfileCustodyEnvelope, "password envelope"),
        password,
        sentinel=_substrate_handle(material.sentinel, custody.ProfileCustodySentinelRecord, "DEK sentinel"),
    )


def profile_is_password_authentication_failure(error: BaseException) -> bool:
    """Recognise only the current custody password-proof refusal."""
    return isinstance(error, custody.ProfileCustodyPasswordError)


def refuse_profile_login_without_password_channel() -> NoReturn:
    """Raise the current custody refusal for an absent explicit password channel."""
    raise custody.ProfileCustodyPasswordError("profile login requires an explicit password channel")


def profile_custody_record_session_material(
    profile_id: UUID,
    *,
    root: Path | None = None,
) -> ProfileCustodyRecordSessionMaterial | None:
    """Return record material only when the live session serves this profile."""
    session = master_key.current_active_bucket_session()
    if session is None or not master_key.session_serves_bucket(session, str(profile_id)):
        return None
    material = load_profile_custody_password_material(profile_id, root=root)
    return ProfileCustodyRecordSessionMaterial(envelope=material.envelope, dek=session.dek)


def profile_bucket_session_open(
    *,
    bucket_id: str,
    kek: bytes,
    dek: bytes,
    idle_minutes: int,
    absolute_minutes: int,
    opened_at: datetime,
    unsecured_backend: bool,
    storage_root: Path,
) -> ProfileBucketSessionPort:
    """Open an authenticated bucket session through the custody substrate."""
    return master_key.BucketSession.open(
        bucket_id=bucket_id,
        kek=kek,
        dek=dek,
        idle_minutes=idle_minutes,
        absolute_minutes=absolute_minutes,
        opened_at=opened_at,
        unsecured_backend=unsecured_backend,
        storage_root=storage_root,
    )


def profile_bucket_session_open_resumed(
    *,
    bucket_id: str,
    dek: bytes,
    idle_minutes: int,
    opened_at: datetime,
    idle_deadline: datetime,
    absolute_deadline: datetime,
    storage_root: Path,
) -> ProfileBucketSessionPort:
    """Re-open a persisted DEK-only bucket session through custody."""
    return master_key.BucketSession.open_resumed(
        bucket_id=bucket_id,
        dek=dek,
        idle_minutes=idle_minutes,
        opened_at=opened_at,
        idle_deadline=idle_deadline,
        absolute_deadline=absolute_deadline,
        storage_root=storage_root,
    )


def profile_current_bucket_session() -> ProfileBucketSessionPort | None:
    """Return the process's current live bucket session, if any."""
    return master_key.current_active_bucket_session()


def profile_session_serves_bucket(session: ProfileBucketSessionPort | None, bucket_id: str) -> bool:
    """Return whether a live bucket session serves the exact profile UUID."""
    resolved = None if session is None else _substrate_handle(session, master_key.BucketSession, "bucket session")
    return bool(master_key.session_serves_bucket(resolved, bucket_id))


def profile_bind_bucket_session(session: ProfileBucketSessionPort) -> None:
    """Bind one authenticated bucket session to the process context."""
    master_key.bind_active_bucket_session(_substrate_handle(session, master_key.BucketSession, "bucket session"))


def profile_close_bucket_session() -> None:
    """Close and clear the current live bucket session."""
    master_key.close_active_bucket_session()


def profile_refuse_unsecured_bucket_with_real_profile(session: ProfileBucketSessionPort) -> None:
    """Apply the real-profile refusal to an unsecured session."""
    master_key.refuse_unsecured_bucket_with_real_profile(
        _substrate_handle(session, master_key.BucketSession, "bucket session")
    )


def profile_zeroise(buffer: object) -> None:
    """Zeroise one custody-owned mutable key buffer."""
    custody.zeroise(buffer)


def profile_is_authentication_failure(error: BaseException) -> bool:
    """Recognise the typed authentication refusals without leaking adapter types."""
    return isinstance(
        error,
        (
            KeyringUnavailableError,
            MasterKeyMaterialMissingError,
        ),
    )


def profile_is_keyring_unavailable(error: BaseException) -> bool:
    """Recognise a keychain persistence refusal for the process-scoped fallback."""
    return isinstance(error, KeyringUnavailableError)


def profile_evaluate_login_throttle(
    *,
    storage_root: Path,
    bucket_id: str,
    now: datetime,
) -> ProfileLoginThrottleEvaluationPort:
    """Evaluate the shared failed-login backoff."""
    return master_key.evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=now)


def profile_record_login_failure(*, storage_root: Path, bucket_id: str, now: datetime) -> None:
    """Record one failed authentication attempt in the shared backoff."""
    master_key.record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)


def profile_reset_login_throttle(*, storage_root: Path, bucket_id: str) -> None:
    """Clear the failed-login backoff after successful authentication."""
    master_key.reset_login_throttle(storage_root=storage_root, bucket_id=bucket_id)


def profile_session_path(*, storage_root: Path, profile_id: UUID) -> Path:
    """Return the persisted profile-session sidecar path."""
    return custody.profile_session_path(storage_root=storage_root, profile_id=profile_id)


def profile_delete_session(*, storage_root: Path, profile_id: UUID) -> None:
    """Revoke the exact persisted session acceleration for one profile."""
    custody.delete_profile_session(storage_root=storage_root, profile_id=profile_id)


def profile_resume_session(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    now: datetime,
) -> tuple[ProfileSessionResumeOutcomePort, bytearray | None]:
    """Evaluate and, when valid, unwrap a persisted profile session.

    The key is yielded as a wipeable buffer the caller owns; see the substrate
    function for why the type is not narrowed to ``bytes`` on the way through.
    """
    return custody.resume_profile_session(
        storage_root=storage_root,
        profile_id=profile_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        now=now,
    )


def profile_advance_session_idle_deadline(
    *,
    storage_root: Path,
    profile_id: UUID,
    record: ProfilePersistedSessionPort,
    new_idle_deadline: datetime,
) -> ProfilePersistedSessionPort:
    """Advance one receipt without exposing its keychain key to the app."""
    return custody.advance_persisted_profile_session_idle_deadline(
        storage_root=storage_root,
        profile_id=profile_id,
        record=_substrate_handle(record, custody.PersistedProfileSession, "persisted session receipt"),
        new_idle_deadline=new_idle_deadline,
    )


def profile_mint_session(
    *,
    storage_root: Path,
    profile_id: UUID,
    custody_generation: int,
    dek_epoch: str,
    dek: bytes,
    now: datetime,
    idle_minutes: int,
    absolute_minutes: int,
) -> ProfilePersistedSessionPort:
    """Mint and custody one optional keyring-accelerated DEK session."""
    return custody.mint_profile_session(
        storage_root=storage_root,
        profile_id=profile_id,
        custody_generation=custody_generation,
        dek_epoch=dek_epoch,
        dek=dek,
        now=now,
        idle_minutes=idle_minutes,
        absolute_minutes=absolute_minutes,
    )


def profile_is_persisted_session(record: object) -> TypeGuard[ProfilePersistedSessionPort]:
    """Return whether an outcome record is the custody-owned persisted model."""
    return isinstance(record, custody.PersistedProfileSession)


def profile_custody_secure_object_namespace() -> ProfileCustodySecureObjectNamespace:
    """Resolve the registered current-profile value namespace at the app boundary."""
    return ProfileCustodySecureObjectNamespace(
        namespace=USER_PROFILE_VALUE_NAMESPACE.namespace,
        sensitivity=USER_PROFILE_VALUE_NAMESPACE.sensitivity,
        schema_version=USER_PROFILE_VALUE_NAMESPACE.schema_version,
    )


def profile_custody_secure_object_key_digest(object_key: str) -> bytes:
    """Derive the opaque object-key digest through the custody provider."""
    return crypto.secure_object_key_digest(object_key)


@contextmanager
def profile_custody_secure_object_repository(
    *,
    profile_id: UUID,
    dek: bytes,
    root: Path,
    database_file: Path | None = None,
) -> Generator[ProfileCustodySecureObjectRepositoryPort]:
    """Open the canonical encrypted-object repository for one profile capsule.

    The provider owns the persistence/runtime imports and the short-lived
    staging session needed before a capsule has been published. Application
    authorities consume only this narrow repository port.
    """
    active = master_key.current_active_bucket_session()
    if database_file is None and master_key.session_serves_bucket(active, str(profile_id)):
        settings = Settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(profile_id))
        yield secure_object_repository_for_bucket(str(profile_id), settings)
        return

    if database_file is None:
        database_file = bucket.bucket_paths(root, str(profile_id)).database_file
    # The DEK binding stays out here on purpose: a staged capsule's key exists
    # only inside the transaction creating it, so it cannot be storage's to
    # resolve. Everything below that -- engine lifetime, namespace registry,
    # session requirement -- is runtime-owned through the staged-bucket door.
    with (
        _temporary_profile_custody_session(profile_id=profile_id, dek=dek, root=root),
        secure_object_repository_for_staged_bucket(str(profile_id), database_file=database_file) as staged,
    ):
        yield staged


@contextmanager
def _temporary_profile_custody_session(*, profile_id: UUID, dek: bytes, root: Path) -> Generator[None]:
    """Bind the just-minted DEK while staging a not-yet-published capsule."""
    now = datetime.now(UTC)
    bridge = master_key.BucketSession.open_resumed(
        bucket_id=str(profile_id),
        dek=dek,
        idle_minutes=1,
        opened_at=now,
        idle_deadline=now + timedelta(minutes=1),
        absolute_deadline=now + timedelta(minutes=1),
        storage_root=root,
    )
    try:
        with master_key.activate_session(bridge):
            yield
    finally:
        bridge.close()


def load_profile_custody_data_file(
    profile_id: UUID,
    relative_name: str,
    *,
    root: Path | None = None,
) -> bytes:
    """Read one committed capsule data member through the custody provider."""
    return custody.load_committed_profile_custody_data_file(profile_id, relative_name, root=root)


def replace_profile_custody_data_file(
    profile_id: UUID,
    relative_name: str,
    payload: bytes,
    *,
    expected_sha256: str,
    root: Path | None = None,
) -> None:
    """CAS-replace one committed capsule data member through custody."""
    custody.replace_committed_profile_custody_data_file(
        profile_id,
        relative_name,
        payload,
        expected_sha256=expected_sha256,
        root=root,
    )


def default_profile_bucket_event_history_repository(
    *,
    objects: ProfileCustodySecureObjectRepositoryPort | None = None,
) -> ProfileCustodyBucketEventHistoryPort:
    """Resolve the encrypted bucket-event repository at the app boundary."""
    resolved = (
        None if objects is None else _substrate_handle(objects, SecureObjectRepository, "secure-object repository")
    )
    return BucketEventHistoryRepository(objects=resolved)


__all__ = [
    "ProfileBucketSessionPort",
    "ProfileBucketStoragePathsPort",
    "ProfileBucketStoragePort",
    "ProfileCustodyBucketEventHistoryPort",
    "ProfileCustodyEnvelopePort",
    "ProfileCustodyLocalRecordStore",
    "ProfileCustodyPasswordMaterialPort",
    "ProfileCustodyRecordSessionMaterial",
    "ProfileCustodyRecoveryEnrollmentMaterial",
    "ProfileCustodyRecoveryEnvelopePort",
    "ProfileCustodyRegistrationMaterial",
    "ProfileCustodySecureObjectNamespace",
    "ProfileCustodySecureObjectRawRowPort",
    "ProfileCustodySecureObjectRecordPort",
    "ProfileCustodySecureObjectRepositoryPort",
    "ProfileCustodySentinelPort",
    "ProfileCustodyUnlockPort",
    "ProfileLoginThrottleEvaluationPort",
    "ProfilePersistedSessionPort",
    "ProfileRecordCryptoError",
    "ProfileRecordCryptoPort",
    "ProfileRecordEncryptedBlob",
    "ProfileRecoveryArtifactWarning",
    "ProfileSecureObjectInventoryPort",
    "ProfileSessionResumeOutcomePort",
    "canonical_snapshot_bytes",
    "canonical_snapshot_digest",
    "canonical_snapshot_payload",
    "committed_profile_custody_inventory",
    "create_profile_custody_registration_material",
    "create_profile_recovery_enrollment_material",
    "default_profile_bucket_event_history_repository",
    "default_profile_bucket_storage",
    "default_profile_custody_local_record_store",
    "default_profile_record_crypto_port",
    "default_profile_secure_object_inventory",
    "ensure_profile_custody_owner_root",
    "export_profile_recovery_artifact",
    "load_profile_custody_data_file",
    "load_profile_custody_password_material",
    "parse_profile_custody_envelope",
    "parse_profile_custody_recovery_envelope",
    "parse_profile_custody_sentinel",
    "profile_advance_session_idle_deadline",
    "profile_bind_bucket_session",
    "profile_bucket_session_open",
    "profile_bucket_session_open_resumed",
    "profile_close_bucket_session",
    "profile_current_bucket_session",
    "profile_custody_owner_root",
    "profile_custody_record_session_material",
    "profile_custody_recovery_envelope_path",
    "profile_custody_secure_object_key_digest",
    "profile_custody_secure_object_namespace",
    "profile_custody_secure_object_repository",
    "profile_delete_session",
    "profile_evaluate_login_throttle",
    "profile_is_authentication_failure",
    "profile_is_keyring_unavailable",
    "profile_is_password_authentication_failure",
    "profile_is_persisted_session",
    "profile_mint_session",
    "profile_record_login_failure",
    "profile_refuse_unsecured_bucket_with_real_profile",
    "profile_reset_login_throttle",
    "profile_resume_session",
    "profile_session_path",
    "profile_session_serves_bucket",
    "profile_zeroise",
    "prove_profile_recovery_artifact",
    "refuse_profile_login_without_password_channel",
    "replace_profile_custody_data_file",
    "replace_profile_custody_envelope",
    "unlock_profile_custody_password",
    "verify_profile_custody_dek_against_sentinel",
]
