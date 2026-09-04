"""Storage-layer exceptions.

All storage errors inherit from :class:`core.errors.CadrumoError` so callers can
catch domain-wide failures with a single base class.

The class tree:

- :class:`StorageError` — base for every storage error.
- :class:`PersistenceError` — base for the at-rest crypto, secret store,
  blob store, envelope, file lock, path containment, and audit-redaction
  surfaces. Subclass of :class:`StorageError` so existing catchers
  continue to work.
"""

from __future__ import annotations

from typing import Final

from collections.abc import Mapping

from ....core.errors.hierarchy import CadrumoError


class SecureStorageError(CadrumoError):
    """Base class for secure-storage failures.

    This named base keeps the encrypted persistence, secret-store,
    bucket-session, and per-bucket lifecycle surfaces catchable as one
    family while still deriving from the central Cadrumo error registry.
    """


class StorageError(SecureStorageError):
    """Base class for every error raised by :mod:`adapters.persistence.storage`."""


class RepositoryError(StorageError):
    """Raised when a repository operation fails (not-found, integrity, etc.)."""


class RepositorySetupError(RepositoryError):
    """Raised when a concrete repository subclass is missing a required class attribute.

    Programming-contract guard: the attribute must be declared on the subclass
    before instantiation. Unlike a plain :class:`TypeError`, this error is
    enrolled in the Cadrumo error registry so it produces a structured envelope
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
    elapsed. The session is sealed. The CLI boundary may project a recovery
    action only after it resolves a public profile target.
    """


class KeyringUnavailableError(SecretStoreError):
    """Raised when the OS keychain backend is unusable.

    Either no backend is registered (e.g. headless Linux without
    libsecret), the backend rejected the operation, or the configured
    backend is the no-op ``null`` keyring.
    """


class MasterKeyUnavailableError(SecretStoreError):
    """Raised when no master key can be acquired from any provider."""


class MasterKeyMaterialMissingError(MasterKeyUnavailableError):
    """Raised when no key material this substrate can open a bucket with exists.

    The shared process-wide key store this once described -- a keyring entry
    and a passphrase-derived file fallback -- was deleted with its providers,
    so the artefacts named here no longer exist to be absent. What survives is
    the same distinction at the current custody boundary: a bucket's data key
    lives in that profile's own password custody, so this class means no
    unlocked custody is
    available rather than a wrong passphrase, and it is raised without minting
    anything.

    Ordinary load paths fail closed with this class rather than provisioning
    on demand, which is what keeps "not provisioned" and "authentication
    failed" separable at the surface.
    """


class UnsecuredModeRefusedError(SecretStoreError):
    """Raised when the unsecured backend is requested without proper gating.

    Two refusal classes:

    1. The unsecured backend was selected (``cadrumo_secret_store_backend=unsecured``)
       but the operator did not set ``CADRUMO_ALLOW_UNENCRYPTED=1``. The hostile-
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
    """Raised when an on-disk envelope version differs from the consumer contract."""


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


class SecureObjectRowIdentityError(PersistenceError):
    """Raised when a stored row's payload does not reconstruct the key it is filed under.

    Every envelope-bound repository derives its object key from the payload's
    own natural identity, so the two are two encodings of one fact and must
    agree. A row whose decrypted payload rebuilds a different key is a
    substituted or misfiled record: the window it was addressed under is not
    the window it describes, and projecting it would let a foreign record
    inherit the addressed row's coordinates.

    Raised by the verifying scan rather than silently skipping the row, because
    a caller counting records for a declaration must never be handed a quietly
    shortened set.
    """

    def __init__(
        self,
        namespace: str,
        *,
        expected_identifier: str,
        payload_identifier: str | None = None,
    ) -> None:
        """Construct the error, naming the key addressed and the identity found.

        ``expected_identifier`` is the natural key the row was addressed under.
        ``payload_identifier`` is the identity the decrypted payload rebuilds,
        supplied where the two are separately known so the refusal names both
        sides of the mismatch rather than leaving the reader to guess which one
        it reported. It is omitted by the enumeration path, where the stored key
        is an HMAC digest and no natural key is recoverable from it -- there the
        rebuilt identity IS the only nameable one.
        """
        context = {"namespace": namespace, "expected_identifier": expected_identifier}
        if payload_identifier is not None:
            context["payload_identifier"] = payload_identifier
        super().__init__(
            context=context,
            translated_message="errors.integrity.integrity_storage_secure_object_row_identity",
        )
        self.namespace = namespace
        self.expected_identifier = expected_identifier
        self.payload_identifier = payload_identifier


class SecretNotFoundError(SecretStoreError):
    """Raised when a secret-store ``get`` does not find a record for the requested key."""


class SecretAlreadyExistsError(SecretStoreError):
    """Raised when a secret-store ``put`` would overwrite an existing key without ``overwrite=True``."""


class RetentionPolicyError(PersistenceError):
    """Raised when a record's retention metadata violates its classification policy."""


class NamespaceRegistryError(StorageError, ValueError):
    """Raised when a namespace-registry key or definition violates a boot-time invariant.

    Fires from Pydantic field and model validators on
    :class:`~adapters.persistence.storage.SecureObjectNamespaceDefinition`,
    :class:`~adapters.persistence.storage.StoragePathDefinition`, and
    :class:`~adapters.persistence.storage.StorageHierarchyRegistry` when a
    registry key, namespace slug, path segment, or uniqueness constraint is
    violated at construction time.  Inherits from :class:`StorageError` and
    ultimately from :class:`~core.errors.CadrumoError` so callers can catch
    it without importing Pydantic internals.

    Because these validators are called by Pydantic during model construction
    the exception propagates wrapped inside a :class:`pydantic.ValidationError`
    when raised from a field validator; direct callers of
    :class:`~adapters.persistence.storage.StorageHierarchyRegistry`
    model validators receive the raw :class:`NamespaceRegistryError`.
    """


#: The storage failures a calculation treats as DEGRADATION rather than a defect:
#: encrypted facts that cannot be read back, so the caller reports an incomplete
#: source instead of a wrong total.
#:
#: Nine modules each spelled this tuple out. Seven carried exactly these three,
#: and two extended it with their own persistence errors -- which is legitimate,
#: and is why extenders compose this tuple rather than restating it. Restating it
#: is how one caller ends up not degrading on an error the others do.
STORAGE_DEGRADATION_ERRORS: Final[tuple[type[Exception], ...]] = (
    ClassificationError,
    DecryptionError,
    EnvelopeVersionError,
)
