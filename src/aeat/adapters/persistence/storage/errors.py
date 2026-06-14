"""Storage-layer exceptions.

All storage errors inherit from :class:`aeat.core.errors.AeatError` so callers can
catch domain-wide failures with a single base class.

The class tree:

- :class:`StorageError` — base for every storage error.
- :class:`PersistenceError` — base for the at-rest crypto, secret store,
  blob store, envelope, file lock, path containment, and audit-redaction
  surfaces. Subclass of :class:`StorageError` so existing catchers
  continue to work.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.errors import AeatError


class SecureStorageError(AeatError):
    """Base class for secure-storage failures.

    This named base keeps the encrypted persistence, secret-store,
    bucket-session, and per-bucket lifecycle surfaces catchable as one
    family while still deriving from the central AEAT error registry.
    """


class StorageError(SecureStorageError):
    """Base class for every error raised by :mod:`aeat.adapters.persistence.storage`."""


class RepositoryError(StorageError):
    """Raised when a repository operation fails (not-found, integrity, etc.)."""


class RepositorySetupError(RepositoryError):
    """Raised when a concrete repository subclass is missing a required class attribute.

    Programming-contract guard: the attribute must be declared on the subclass
    before instantiation. Unlike a plain :class:`TypeError`, this error is
    enrolled in the AEAT error registry so it produces a structured envelope
    rather than an opaque interpreter-level exception.
    """


class SecureObjectRevisionConflictError(RepositoryError):
    """Raised when a revision-aware secure-object write sees a stale revision."""


class PersistenceError(StorageError):
    """Base class for governed-persistence error subtypes.

    Errors raised by the at-rest crypto primitives, the secret store, the
    encrypted blob store, the schema-version envelope, the file-lock helper,
    the path containment helper, and the audit-sink redaction contract all
    inherit from this class.
    """


class StorageValidationError(PersistenceError, ValueError):
    """Raised when a storage parameter fails validation (e.g. key length).

    Inherits from both :class:`PersistenceError` and :class:`ValueError`
    to remain compatible with Pydantic's validator-failure contract while
    allowing catch-all :class:`StorageError` handlers to detect integrity
    failures.
    """


_STORAGE_VALIDATION_MESSAGE_KEY = "errors.integrity.integrity_storage_validation"


def storage_validation_error(message: str) -> StorageValidationError:
    """Build a :class:`StorageValidationError` carrying the shared integrity message key.

    Single canonical factory for the storage-validation error that the
    persistence-storage submodules (crypto, envelope, runtime, secret store,
    and the master-key helpers) previously each declared identically.
    """
    return StorageValidationError(message, translated_message=_STORAGE_VALIDATION_MESSAGE_KEY)


class EncryptionError(PersistenceError):
    """Base class for AEAD encryption / decryption failures."""


class DecryptionError(EncryptionError):
    """Raised when AEAD decryption fails (tag mismatch, malformed input)."""


class SecureObjectUnreadableError(DecryptionError):
    """Raised when one stored secure object cannot be decrypted under the current master key.

    Distinct from the generic :class:`DecryptionError` so iterator-shaped
    consumers can surface a structured per-row failure (namespace, row id,
    underlying cause) without aborting the iteration. The plaintext bound
    to such a row is cryptographically unrecoverable from this process: the
    master key under which it was sealed is no longer available.
    """

    def __init__(self, namespace: str, row_id: int, *, cause: BaseException | None = None) -> None:
        """Construct the error, binding the affected namespace, row identifier, and optional root cause."""
        super().__init__(
            context={"namespace": namespace, "row_id": row_id},
            translated_message="errors.integrity.integrity_storage_secure_object_unreadable",
        )
        self.namespace = namespace
        self.row_id = row_id
        self.__cause__ = cause


class KeyDerivationError(EncryptionError):
    """Raised when a key-derivation step fails."""


class NonceCollisionError(EncryptionError):
    """Raised on a defensive nonce-uniqueness invariant violation."""


class SecretStoreError(PersistenceError):
    """Base class for secret-store I/O failures."""


class SessionExpiredError(SecretStoreError):
    """Raised when the active :class:`BucketSession` has crossed its idle deadline.

    The session was opened earlier in the process lifetime but the
    operator did not act before the configured idle-lock window
    elapsed. The session is sealed; the operator must re-activate by
    running ``aeat config switch NAME`` (or a subsequent
    bootstrap-exempt verb that opens a fresh session).
    """


class PassphraseTooShortError(SecretStoreError):
    """Raised when an operator-supplied passphrase falls below the NIST floor.

    NIST SP 800-63B §5.1.1.1 mandates that verifiers SHALL require user-
    chosen memorized secrets to be at least 8 characters in length. The
    :class:`FileFallbackMasterKeyProvider` rejects shorter passphrases at
    resolution time.
    """


class KeyringUnavailableError(SecretStoreError):
    """Raised when the OS keychain backend is unusable.

    Either no backend is registered (e.g. headless Linux without
    libsecret), the backend rejected the operation, or the configured
    backend is the no-op ``null`` keyring.
    """


class MasterKeyUnavailableError(SecretStoreError):
    """Raised when no master key can be acquired from any provider."""


class MasterKeyKdfVersionError(MasterKeyUnavailableError):
    """Raised when the on-disk ``master.kdf`` declares a KDF version this build cannot consume.

    The substrate gates the master.kdf parameters by version. Mismatch means
    the operator's passphrase may be correct, but the on-disk parameters do not
    match this build's supported key-derivation contract.
    """


class MasterKeyKeychainLockedError(MasterKeyUnavailableError):
    """Raised when the OS keychain is reachable but the entry is locked.

    Distinct from :class:`KeyringUnavailableError` (no usable backend at
    all). This class signals a recoverable state: the operator unlocks
    the OS keychain (Touch ID / Windows Hello / desktop-wallet unlock)
    and retries. The CLI's error envelope renders the actionable hint.
    """


class MasterKeyPassphraseMismatchError(MasterKeyUnavailableError):
    """Raised when the file-fallback passphrase does not unwrap ``master.key``.

    Recoverable by re-entering the passphrase. If the passphrase has
    been forgotten, the operator can use
    ``aeat config recover`` to re-mint the master key
    from a recovery-key backup. The CLI's error envelope distinguishes
    this case from :class:`MasterKeyMaterialMissingError` so retries
    do not waste backoff budget on missing-file errors.
    """


class MasterKeyMaterialMissingError(MasterKeyUnavailableError):
    """Raised when no master-key material exists at all.

    Neither the keyring entry nor the file-fallback artefacts
    (``master.key`` / ``master.kdf`` / ``salt``) are present. The
    substrate has not been provisioned. The operator's actionable
    next step is ``aeat config profile create NAME`` or, if a recovery key
    is available, ``aeat config recover``.

    Raised by canonical read paths to distinguish "not provisioned"
    from "wrong passphrase" without minting key material. Explicit
    profile creation is responsible for provisioning; ordinary load
    paths fail closed with this class when material is absent.
    """


class UnsecuredModeRefusedError(SecretStoreError):
    """Raised when the unsecured backend is requested without proper gating.

    Two refusal classes:

    1. The unsecured backend was selected (``aeat_secret_store_backend=unsecured``)
       but the operator did not set ``AEAT_ALLOW_UNENCRYPTED=1``. The hostile-
       named env var is the legible-and-embarrassing opt-out gate.
    2. The unsecured backend is active AND the operator profile carries a
       real NIF/NIE/CIF (NIF-canary). Real tax data is incompatible with a
       published deterministic master key; the substrate refuses to write
       such records into the unsecured store.
    """


class ClassificationError(PersistenceError):
    """Raised when a record's declared sensitivity class is incompatible with its repository.

    Example: writing a CORPUS-class blob through the encrypted-blob path,
    or loading an envelope under a different classification than the
    one persisted on disk.
    """


class EnvelopeVersionError(PersistenceError):
    """Raised when an on-disk envelope is older or newer than the consumer expects.

    Older envelopes may be migrated forward via
    ``migrate_envelope``; newer envelopes are not safely
    consumable by older code and refuse to load.
    """


class PathContainmentError(PersistenceError, ValueError):
    """Raised when a computed path escapes its configured root directory."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Construct a path-containment error with localized operator output."""
        super().__init__(
            message,
            context=context,
            translated_message="errors.integrity.integrity_storage_path_containment",
        )


class BlobNotFoundError(PersistenceError):
    """Raised when a blob lookup misses on the encrypted blob store."""


class BlobIntegrityError(PersistenceError):
    """Raised when a blob's on-disk SHA-256 disagrees with its manifest."""


class SecretNotFoundError(SecretStoreError):
    """Raised when a secret-store ``get`` does not find a record for the requested key."""


class SecretAlreadyExistsError(SecretStoreError):
    """Raised when a secret-store ``put`` would overwrite an existing key without ``overwrite=True``."""


class RetentionPolicyError(PersistenceError):
    """Raised when a record's retention metadata violates its classification policy."""


class NamespaceRegistryError(StorageError, ValueError):
    """Raised when a namespace-registry key or definition violates a boot-time invariant.

    Fires from Pydantic field and model validators on
    :class:`~aeat.adapters.persistence.storage.SecureObjectNamespaceDefinition`,
    :class:`~aeat.adapters.persistence.storage.StoragePathDefinition`, and
    :class:`~aeat.adapters.persistence.storage.StorageHierarchyRegistry` when a
    registry key, namespace slug, path segment, or uniqueness constraint is
    violated at construction time.  Inherits from :class:`StorageError` and
    ultimately from :class:`~aeat.core.errors.AeatError` so callers can catch
    it without importing Pydantic internals.

    Because these validators are called by Pydantic during model construction
    the exception propagates wrapped inside a :class:`pydantic.ValidationError`
    when raised from a field validator; direct callers of
    :class:`~aeat.adapters.persistence.storage.StorageHierarchyRegistry`
    model validators receive the raw :class:`NamespaceRegistryError`.
    """
