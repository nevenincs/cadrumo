"""Application-owned ports for profile-custody local records.

Application services consume this narrow record store instead of reaching into
the persistence adapter. The default provider resolves the real custody
adapter at the composition boundary; callers can inject the same port when a
different storage root or lifecycle is being composed.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, Protocol, TypeGuard, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...core import ProfileSessionRefusalReason, SecureObjectWrite, StorageCategory, storage_location
from ...core.classification import SensitivityClass
from ...core.config import SecretStoreBackend, Settings
from ...core.hashing import bounded_canonical_json_bytes, canonical_json_digest
from ...core.paths import effective_storage_root

if TYPE_CHECKING:
    from ...domain.buckets import BucketEventHistoryCatalogue
    from ..user_profile._custody_ports import (
        ProfileCustodyEnvelopePort,
        ProfileCustodySentinelPort,
    )


class ProfileRecordCryptoError(RuntimeError):
    """The configured profile-record crypto provider rejected an operation."""


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


class _PersistenceKdfCalibration(Protocol):
    parameters: object


class _PersistenceRegistrationModule(Protocol):
    calibrate_profile_kdf: Callable[..., _PersistenceKdfCalibration]
    create_profile_custody_password_envelope: Callable[..., ProfileCustodyEnvelopePort]
    create_profile_custody_sentinel: Callable[..., ProfileCustodySentinelPort]


class ProfileCustodyPasswordMaterialPort(Protocol):
    """Normal-password material exposed by the custody read boundary."""

    envelope: ProfileCustodyEnvelopePort
    sentinel: ProfileCustodySentinelPort


class ProfileCustodyUnlockPort(Protocol):
    """A current-envelope DEK accepted only after the sentinel proof."""

    profile_id: UUID
    envelope_digest: str
    dek: bytes


class _PersistencePasswordModule(Protocol):
    load_committed_profile_password_material: Callable[..., ProfileCustodyPasswordMaterialPort]
    unlock_profile_custody: Callable[..., ProfileCustodyUnlockPort]


class ProfileCustodyBucketSessionPort(Protocol):
    """The live-session fields needed by an authenticated record reader."""

    bucket_id: str
    dek: bytes


class ProfileMasterKeyProviderPort(Protocol):
    """Master-key provider capability exposed to profile application services."""

    def get_master_key(self) -> bytes:
        """Unwrap and return the authenticated master key."""
        ...


class ProfileBucketSessionPort(Protocol):
    """Live bucket-session capability exposed across the application boundary."""

    bucket_id: str
    dek: bytes
    idle_deadline: datetime
    absolute_deadline: datetime
    opened_at: datetime
    unsecured_backend: bool

    def touch(self, now: datetime) -> None:
        """Advance the sliding idle deadline."""
        ...

    def is_expired(self, now: datetime) -> bool:
        """Return whether this session has crossed either deadline."""
        ...

    def close(self) -> None:
        """Zeroise and retire this session's local key material."""
        ...


class ProfilePersistedSessionPort(Protocol):
    """Persisted session record fields needed by login orchestration."""

    bucket_id: str
    backend_kind: SecretStoreBackend
    authenticated_at: datetime
    idle_deadline: datetime
    absolute_deadline: datetime


class ProfileSessionResumeOutcomePort(Protocol):
    """Fail-closed persisted-session evaluation result."""

    resumed: bool
    refusal: ProfileSessionRefusalReason | None
    record: ProfilePersistedSessionPort | None


class ProfileLoginThrottleEvaluationPort(Protocol):
    """Failed-login backoff decision exposed to the application."""

    throttled: bool
    remaining_seconds: int


class ProfileCustodySecureObjectRawRowPort(Protocol):
    """Metadata and payload fields exposed by one secure-object row."""

    namespace: str
    object_key: bytes
    payload: bytes
    revision_id: str | None
    previous_revision_id: str | None
    payload_hash: str | None
    ciphertext_hash: str | None
    write_provenance: str | None
    source_event_id: str | None


class ProfileCustodySecureObjectRecordPort(Protocol):
    """Decrypted secure-object payload and its CAS revision token."""

    revision_id: str
    payload: bytes


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


class _PersistenceMasterKeyModule(Protocol):
    current_active_bucket_session: Callable[..., object | None]
    session_serves_bucket: Callable[..., bool]


class _PersistenceSecureObjectModule(Protocol):
    STORAGE_NAMESPACE_REGISTRY: object
    USER_PROFILE_VALUE_NAMESPACE: _PersistenceNamespaceDefinition
    SecureObjectRepository: Callable[..., ProfileCustodySecureObjectRepositoryPort]


class _PersistenceNamespaceDefinition(Protocol):
    namespace: str
    sensitivity: SensitivityClass
    schema_version: int


class _PersistenceRuntimeRepositoryModule(Protocol):
    secure_object_repository_for_bucket: Callable[..., ProfileCustodySecureObjectRepositoryPort]


class _PersistenceSqlEngineModule(Protocol):
    create_engine_from_settings: Callable[..., _PersistenceEngine]


class _PersistenceEngine(Protocol):
    def dispose(self) -> None: ...


class _PersistenceBucketPathModule(Protocol):
    bucket_paths: Callable[..., _PersistenceBucketPaths]


class _PersistenceBucketPaths(Protocol):
    database_file: Path


class _PersistenceBucketEventModule(Protocol):
    BucketEventHistoryRepository: Callable[..., ProfileCustodyBucketEventHistoryPort]


class _PersistenceProfileDataModule(Protocol):
    load_committed_profile_custody_data_file: Callable[..., bytes]
    replace_committed_profile_custody_data_file: Callable[..., None]


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


class ProfileBucketStoragePathsPort(Protocol):
    """Resolved filesystem paths for one profile bucket."""

    bucket_dir: Path
    db_dir: Path
    blobs_dir: Path
    database_file: Path


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


class _PersistenceCustodyModule(Protocol):
    clear_profile_custody_local_record: Callable[[Path], None]
    ensure_profile_custody_local_directory: Callable[[Path], None]
    profile_custody_local_lock: Callable[..., AbstractContextManager[None]]
    read_profile_custody_local_record: Callable[..., bytes]
    read_optional_profile_custody_local_record: Callable[..., bytes | None]
    write_profile_custody_local_record: Callable[..., None]


class _PersistenceBucketStorageModule(Protocol):
    bucket_paths: Callable[..., ProfileBucketStoragePathsPort]
    acquire_lock: Callable[..., None]
    release_lock: Callable[..., None]


class _PersistenceActiveStorageModule(Protocol):
    secure_object_repository_for_active_bucket: Callable[..., ProfileSecureObjectInventoryPort]


class _PersistenceEncryptedBlob(Protocol):
    nonce: bytes
    ciphertext: bytes


class _PersistenceCryptoModule(Protocol):
    EncryptedBlob: Callable[..., _PersistenceEncryptedBlob]
    encrypt_record: Callable[..., _PersistenceEncryptedBlob]
    decrypt_record: Callable[..., bytes]


class _PersistenceProfileCustodyLocalRecordStore:
    """Adapt the real persistence facade to the application-owned port."""

    def __init__(self) -> None:
        custody = cast(
            _PersistenceCustodyModule,
            import_module("cadrumo.adapters.persistence.storage.custody"),
        )
        self._clear = custody.clear_profile_custody_local_record
        self._ensure_directory = custody.ensure_profile_custody_local_directory
        self._lock = custody.profile_custody_local_lock
        self._read = custody.read_profile_custody_local_record
        self._read_optional = custody.read_optional_profile_custody_local_record
        self._write = custody.write_profile_custody_local_record

    def ensure_directory(self, path: Path) -> None:
        self._ensure_directory(path)

    def lock(self, path: Path, *, timeout_seconds: float = 30.0) -> AbstractContextManager[None]:
        return self._lock(path, timeout_seconds=timeout_seconds)

    def read(self, path: Path, *, maximum_bytes: int) -> bytes:
        return self._read(path, maximum_bytes=maximum_bytes)

    def read_optional(self, path: Path, *, maximum_bytes: int) -> bytes | None:
        return self._read_optional(path, maximum_bytes=maximum_bytes)

    def write(self, path: Path, payload: bytes, *, publish_once: bool) -> None:
        self._write(path, payload, publish_once=publish_once)

    def clear(self, path: Path) -> None:
        self._clear(path)


class _PersistenceProfileBucketStorage:
    """Adapt canonical bucket layout and locking to the application port."""

    def __init__(self) -> None:
        bucket = cast(
            _PersistenceBucketStorageModule,
            import_module("cadrumo.adapters.persistence.storage.bucket"),
        )
        self._resolve = bucket.bucket_paths
        self._acquire = bucket.acquire_lock
        self._release = bucket.release_lock

    def resolve(self, root: Path, bucket_id: str) -> ProfileBucketStoragePathsPort:
        return self._resolve(root, bucket_id)

    def acquire_lock(self, paths: ProfileBucketStoragePathsPort, *, wait_seconds: float) -> None:
        self._acquire(paths, wait_seconds=wait_seconds)

    def release_lock(self, paths: ProfileBucketStoragePathsPort) -> None:
        self._release(paths)


class _PersistenceProfileSecureObjectInventory:
    """Adapt the active runtime repository to the inventory port."""

    def __init__(self) -> None:
        storage = cast(
            _PersistenceActiveStorageModule,
            import_module("cadrumo.adapters.persistence.storage"),
        )
        repository = storage.secure_object_repository_for_active_bucket()
        self._list_namespaces = repository.list_namespaces
        self._list_keys = repository.list_keys

    def list_namespaces(self) -> tuple[str, ...]:
        return self._list_namespaces()

    def list_keys(self, namespace: str) -> tuple[str, ...]:
        return self._list_keys(namespace)


class _PersistenceProfileRecordCrypto:
    """Adapt the real persistence crypto facade to the application port."""

    def __init__(self) -> None:
        crypto = cast(
            _PersistenceCryptoModule,
            import_module("cadrumo.adapters.persistence.storage.crypto"),
        )
        self._encrypted_blob = crypto.EncryptedBlob
        self._encrypt = crypto.encrypt_record
        self._decrypt = crypto.decrypt_record

    def encrypt_record(
        self,
        plaintext: bytes,
        *,
        key: bytes,
        associated_data: bytes | None = None,
    ) -> ProfileRecordEncryptedBlob:
        try:
            blob = self._encrypt(plaintext, key=key, associated_data=associated_data)
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
            adapter_blob = self._encrypted_blob(nonce=blob.nonce, ciphertext=blob.ciphertext)
            return self._decrypt(adapter_blob, key=key, associated_data=associated_data)
        except Exception as exc:
            raise ProfileRecordCryptoError("profile record decryption failed") from exc


def default_profile_custody_local_record_store() -> ProfileCustodyLocalRecordStore:
    """Return the production custody adapter through the application port."""
    return _PersistenceProfileCustodyLocalRecordStore()


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
) -> ProfileCustodyRegistrationMaterial:
    """Mint the password envelope and DEK sentinel at the custody boundary."""
    custody = cast(
        _PersistenceRegistrationModule,
        import_module("cadrumo.adapters.persistence.storage.custody"),
    )
    calibration = custody.calibrate_profile_kdf(salt=salt)
    envelope = custody.create_profile_custody_password_envelope(
        profile_id=profile_id,
        password=password,
        dek=dek,
        dek_epoch=dek_epoch,
        kdf=calibration.parameters,
    )
    sentinel = custody.create_profile_custody_sentinel(envelope=envelope, dek=dek)
    return ProfileCustodyRegistrationMaterial(envelope=envelope, sentinel=sentinel)


def load_profile_custody_password_material(
    profile_id: UUID,
    *,
    root: Path | None = None,
) -> ProfileCustodyPasswordMaterialPort:
    """Load the normal-password envelope through the custody provider."""
    custody = cast(
        _PersistencePasswordModule,
        import_module("cadrumo.adapters.persistence.storage.custody"),
    )
    return custody.load_committed_profile_password_material(profile_id, root=root)


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
    custody = cast(
        _PersistencePasswordModule,
        import_module("cadrumo.adapters.persistence.storage.custody"),
    )
    return custody.unlock_profile_custody(material.envelope, password, sentinel=material.sentinel)


def profile_is_password_authentication_failure(error: BaseException) -> bool:
    """Recognise only the current custody password-proof refusal."""
    custody = import_module("cadrumo.adapters.persistence.storage.custody")
    return isinstance(error, custody.ProfileCustodyPasswordError)


def refuse_profile_login_without_password_channel() -> NoReturn:
    """Raise the current custody refusal for an absent explicit password channel."""
    custody = import_module("cadrumo.adapters.persistence.storage.custody")
    raise custody.ProfileCustodyPasswordError("profile login requires an explicit password channel")


def profile_custody_record_session_material(
    profile_id: UUID,
    *,
    root: Path | None = None,
) -> ProfileCustodyRecordSessionMaterial | None:
    """Return record material only when the live session serves this profile."""
    master_key = cast(
        _PersistenceMasterKeyModule,
        import_module("cadrumo.adapters.persistence.storage.master_key"),
    )
    active = master_key.current_active_bucket_session()
    session = cast(ProfileCustodyBucketSessionPort | None, active)
    if session is None or not master_key.session_serves_bucket(session, str(profile_id)):
        return None
    material = load_profile_custody_password_material(profile_id, root=root)
    return ProfileCustodyRecordSessionMaterial(envelope=material.envelope, dek=session.dek)


def profile_get_master_key_provider(
    *,
    passphrase_callback: Callable[[], str] | None = None,
) -> ProfileMasterKeyProviderPort:
    """Resolve the configured master-key provider at the custody boundary."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        ProfileMasterKeyProviderPort, master_key.get_master_key_provider(passphrase_callback=passphrase_callback)
    )


def profile_master_key_backend_kind(provider: ProfileMasterKeyProviderPort) -> SecretStoreBackend:
    """Map one resolved provider to the public backend-kind enum."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    if isinstance(provider, master_key.KeyringMasterKeyProvider):
        return SecretStoreBackend.KEYRING
    if isinstance(provider, master_key.FileFallbackMasterKeyProvider):
        return SecretStoreBackend.FILE
    return SecretStoreBackend.UNSECURED


def profile_master_key_is_unsecured(provider: ProfileMasterKeyProviderPort) -> bool:
    """Return whether the resolved provider is the explicitly unsecured backend."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return isinstance(provider, master_key.UnsecuredMasterKeyProvider)


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
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        ProfileBucketSessionPort,
        master_key.BucketSession.open(
            bucket_id=bucket_id,
            kek=kek,
            dek=dek,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
            opened_at=opened_at,
            unsecured_backend=unsecured_backend,
            storage_root=storage_root,
        ),
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
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        ProfileBucketSessionPort,
        master_key.BucketSession.open_resumed(
            bucket_id=bucket_id,
            dek=dek,
            idle_minutes=idle_minutes,
            opened_at=opened_at,
            idle_deadline=idle_deadline,
            absolute_deadline=absolute_deadline,
            storage_root=storage_root,
        ),
    )


def profile_current_bucket_session() -> ProfileBucketSessionPort | None:
    """Return the process's current live bucket session, if any."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(ProfileBucketSessionPort | None, master_key.current_active_bucket_session())


def profile_session_serves_bucket(session: ProfileBucketSessionPort | None, bucket_id: str) -> bool:
    """Return whether a live bucket session serves the exact profile UUID."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return bool(master_key.session_serves_bucket(session, bucket_id))


def profile_bind_bucket_session(session: ProfileBucketSessionPort) -> None:
    """Bind one authenticated bucket session to the process context."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.bind_active_bucket_session(session)


def profile_close_bucket_session() -> None:
    """Close and clear the current live bucket session."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.close_active_bucket_session()


def profile_load_or_mint_bucket_dek(
    *,
    kek: bytes,
    storage_root: Path,
    bucket_id: str,
) -> bytes:
    """Load the existing wrapped bucket DEK without permitting bootstrap minting."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        bytes,
        master_key.load_or_mint_bucket_dek(
            kek=kek,
            storage_root=storage_root,
            bucket_id=bucket_id,
            allow_bootstrap_mint=False,
        ),
    )


def profile_refuse_unsecured_bucket_with_real_profile(session: ProfileBucketSessionPort) -> None:
    """Apply the real-profile refusal to an unsecured session."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.refuse_unsecured_bucket_with_real_profile(session)


def profile_zeroise(buffer: object) -> None:
    """Zeroise one custody-owned mutable key buffer."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.zeroise(buffer)


def profile_is_authentication_failure(error: BaseException) -> bool:
    """Recognise the typed authentication refusals without leaking adapter types."""
    errors = cast(Any, import_module("cadrumo.adapters.persistence.storage.errors"))
    return isinstance(
        error,
        (
            errors.MasterKeyPassphraseMismatchError,
            errors.MasterKeyKeychainLockedError,
            errors.KeyringUnavailableError,
            errors.MasterKeyMaterialMissingError,
        ),
    )


def profile_is_keyring_unavailable(error: BaseException) -> bool:
    """Recognise a keychain persistence refusal for the process-scoped fallback."""
    errors = cast(Any, import_module("cadrumo.adapters.persistence.storage.errors"))
    return isinstance(error, errors.KeyringUnavailableError)


def profile_evaluate_login_throttle(
    *,
    storage_root: Path,
    bucket_id: str,
    now: datetime,
) -> ProfileLoginThrottleEvaluationPort:
    """Evaluate the shared failed-login backoff."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        ProfileLoginThrottleEvaluationPort,
        master_key.evaluate_login_throttle(storage_root=storage_root, bucket_id=bucket_id, now=now),
    )


def profile_record_login_failure(*, storage_root: Path, bucket_id: str, now: datetime) -> None:
    """Record one failed authentication attempt in the shared backoff."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.record_login_failure(storage_root=storage_root, bucket_id=bucket_id, now=now)


def profile_reset_login_throttle(*, storage_root: Path, bucket_id: str) -> None:
    """Clear the failed-login backoff after successful authentication."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.reset_login_throttle(storage_root=storage_root, bucket_id=bucket_id)


def profile_session_idle_minutes(*, storage_root: Path, bucket_id: str, default_minutes: int) -> int:
    """Resolve the current profile's sliding idle window."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return int(
        master_key.idle_minutes_for_bucket(
            storage_root=storage_root,
            bucket_id=bucket_id,
            default_minutes=default_minutes,
        )
    )


def profile_session_absolute_minutes(*, storage_root: Path, bucket_id: str, default_minutes: int) -> int:
    """Resolve the current profile's immutable session cap."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return int(
        master_key.session_absolute_minutes_for_bucket(
            storage_root=storage_root,
            bucket_id=bucket_id,
            default_minutes=default_minutes,
        )
    )


def profile_session_path(*, storage_root: Path, bucket_id: str) -> Path:
    """Return the persisted profile-session sidecar path."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(Path, master_key.profile_session_path(storage_root=storage_root, bucket_id=bucket_id))


def profile_load_session_key(*, bucket_id: str) -> bytes | None:
    """Load the split-knowledge session key from custody."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(bytes | None, master_key.load_profile_session_key(bucket_id=bucket_id))


def profile_delete_session(*, storage_root: Path, bucket_id: str) -> None:
    """Delete both persisted session artefacts for one bucket."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.delete_profile_session(storage_root=storage_root, bucket_id=bucket_id)


def profile_resume_session(
    *,
    storage_root: Path,
    bucket_id: str,
    now: datetime,
) -> tuple[ProfileSessionResumeOutcomePort, bytes | None]:
    """Evaluate and, when valid, unwrap a persisted profile session."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        tuple[ProfileSessionResumeOutcomePort, bytes | None],
        master_key.resume_profile_session(storage_root=storage_root, bucket_id=bucket_id, now=now),
    )


def profile_advance_session_idle_deadline(
    *,
    record: ProfilePersistedSessionPort,
    session_key: bytes,
    new_idle_deadline: datetime,
) -> ProfilePersistedSessionPort:
    """Advance and rewrap one persisted session record."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        ProfilePersistedSessionPort,
        master_key.advance_profile_session_idle_deadline(
            record=record,
            session_key=session_key,
            new_idle_deadline=new_idle_deadline,
        ),
    )


def profile_write_session(
    *,
    storage_root: Path,
    bucket_id: str,
    record: ProfilePersistedSessionPort,
) -> None:
    """Persist one authenticated profile-session record."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    master_key.write_profile_session(storage_root=storage_root, bucket_id=bucket_id, record=record)


def profile_mint_session(
    *,
    storage_root: Path,
    bucket_id: str,
    dek: bytes,
    now: datetime,
    idle_minutes: int,
    absolute_minutes: int,
) -> ProfilePersistedSessionPort:
    """Mint and custody one optional keyring-accelerated DEK session."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return cast(
        ProfilePersistedSessionPort,
        master_key.mint_profile_session(
            storage_root=storage_root,
            bucket_id=bucket_id,
            # This field describes the session-key custodian, never the
            # password authority. Normal login authenticates through the
            # profile's current envelope and sentinel before it reaches here.
            backend_kind=SecretStoreBackend.KEYRING,
            dek=dek,
            now=now,
            idle_minutes=idle_minutes,
            absolute_minutes=absolute_minutes,
        ),
    )


def profile_is_persisted_session(record: object) -> TypeGuard[ProfilePersistedSessionPort]:
    """Return whether an outcome record is the custody-owned persisted model."""
    master_key = cast(Any, import_module("cadrumo.adapters.persistence.storage.master_key"))
    return isinstance(record, master_key.PersistedProfileSession)


def profile_custody_secure_object_namespace() -> ProfileCustodySecureObjectNamespace:
    """Resolve the registered current-profile value namespace at the app boundary."""
    storage = cast(
        _PersistenceSecureObjectModule,
        import_module("cadrumo.adapters.persistence.storage"),
    )
    definition = storage.USER_PROFILE_VALUE_NAMESPACE
    return ProfileCustodySecureObjectNamespace(
        namespace=definition.namespace,
        sensitivity=definition.sensitivity,
        schema_version=definition.schema_version,
    )


def profile_custody_secure_object_key_digest(object_key: str) -> bytes:
    """Derive the opaque object-key digest through the custody provider."""
    crypto = import_module("cadrumo.adapters.persistence.storage.crypto")
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
    master_key = import_module("cadrumo.adapters.persistence.storage.master_key")
    active = master_key.current_active_bucket_session()
    if database_file is None and master_key.session_serves_bucket(active, str(profile_id)):
        runtime = cast(
            _PersistenceRuntimeRepositoryModule,
            import_module("cadrumo.adapters.persistence.storage.runtime_repository"),
        )
        settings = Settings(cadrumo_local_storage_root=root, cadrumo_active_profile=str(profile_id))
        yield runtime.secure_object_repository_for_bucket(str(profile_id), settings)
        return

    if database_file is None:
        buckets = cast(
            _PersistenceBucketPathModule,
            import_module("cadrumo.adapters.persistence.storage.bucket"),
        )
        database_file = buckets.bucket_paths(root, str(profile_id)).database_file
    database_file.parent.mkdir(parents=True, exist_ok=True)
    settings = Settings(cadrumo_database_url=f"sqlite:///{database_file.as_posix()}")
    with _temporary_profile_custody_session(profile_id=profile_id, dek=dek, root=root):
        sql = cast(
            _PersistenceSqlEngineModule,
            import_module("cadrumo.adapters.persistence.storage.sql.engine"),
        )
        storage = cast(
            _PersistenceSecureObjectModule,
            import_module("cadrumo.adapters.persistence.storage"),
        )
        engine = sql.create_engine_from_settings(settings)
        try:
            yield storage.SecureObjectRepository(
                engine=engine,
                namespace_registry=storage.STORAGE_NAMESPACE_REGISTRY,
                active_session_bucket_id=str(profile_id),
                require_secure_active_session=True,
            )
        finally:
            engine.dispose()


@contextmanager
def _temporary_profile_custody_session(*, profile_id: UUID, dek: bytes, root: Path) -> Generator[None]:
    """Bind the just-minted DEK while staging a not-yet-published capsule."""
    master_key = import_module("cadrumo.adapters.persistence.storage.master_key")
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
    custody = cast(
        _PersistenceProfileDataModule,
        import_module("cadrumo.adapters.persistence.storage.custody"),
    )
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
    custody = cast(
        _PersistenceProfileDataModule,
        import_module("cadrumo.adapters.persistence.storage.custody"),
    )
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
    buckets = cast(
        _PersistenceBucketEventModule,
        import_module("cadrumo.adapters.persistence.profile.buckets"),
    )
    return buckets.BucketEventHistoryRepository(objects=objects)


__all__ = [
    "ProfileBucketSessionPort",
    "ProfileBucketStoragePathsPort",
    "ProfileBucketStoragePort",
    "ProfileCustodyBucketEventHistoryPort",
    "ProfileCustodyBucketSessionPort",
    "ProfileCustodyLocalRecordStore",
    "ProfileCustodyPasswordMaterialPort",
    "ProfileCustodyRecordSessionMaterial",
    "ProfileCustodyRegistrationMaterial",
    "ProfileCustodySecureObjectNamespace",
    "ProfileCustodySecureObjectRawRowPort",
    "ProfileCustodySecureObjectRecordPort",
    "ProfileCustodySecureObjectRepositoryPort",
    "ProfileCustodyUnlockPort",
    "ProfileLoginThrottleEvaluationPort",
    "ProfileMasterKeyProviderPort",
    "ProfilePersistedSessionPort",
    "ProfileRecordCryptoError",
    "ProfileRecordCryptoPort",
    "ProfileRecordEncryptedBlob",
    "ProfileSecureObjectInventoryPort",
    "ProfileSessionResumeOutcomePort",
    "canonical_snapshot_bytes",
    "canonical_snapshot_digest",
    "canonical_snapshot_payload",
    "create_profile_custody_registration_material",
    "default_profile_bucket_event_history_repository",
    "default_profile_bucket_storage",
    "default_profile_custody_local_record_store",
    "default_profile_record_crypto_port",
    "default_profile_secure_object_inventory",
    "ensure_profile_custody_owner_root",
    "load_profile_custody_data_file",
    "load_profile_custody_password_material",
    "profile_advance_session_idle_deadline",
    "profile_bind_bucket_session",
    "profile_bucket_session_open",
    "profile_bucket_session_open_resumed",
    "profile_close_bucket_session",
    "profile_current_bucket_session",
    "profile_custody_owner_root",
    "profile_custody_record_session_material",
    "profile_custody_secure_object_key_digest",
    "profile_custody_secure_object_namespace",
    "profile_custody_secure_object_repository",
    "profile_delete_session",
    "profile_evaluate_login_throttle",
    "profile_get_master_key_provider",
    "profile_is_authentication_failure",
    "profile_is_keyring_unavailable",
    "profile_is_password_authentication_failure",
    "profile_is_persisted_session",
    "profile_load_or_mint_bucket_dek",
    "profile_load_session_key",
    "profile_master_key_backend_kind",
    "profile_master_key_is_unsecured",
    "profile_mint_session",
    "profile_record_login_failure",
    "profile_refuse_unsecured_bucket_with_real_profile",
    "profile_reset_login_throttle",
    "profile_resume_session",
    "profile_session_absolute_minutes",
    "profile_session_idle_minutes",
    "profile_session_path",
    "profile_session_serves_bucket",
    "profile_write_session",
    "profile_zeroise",
    "refuse_profile_login_without_password_channel",
    "replace_profile_custody_data_file",
    "unlock_profile_custody_password",
]
