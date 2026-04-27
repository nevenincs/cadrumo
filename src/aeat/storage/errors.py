"""Storage-layer exceptions.

All storage errors inherit from :class:`aeat.errors.AeatError` so callers can
catch domain-wide failures with a single base class.

The class tree:

- :class:`StorageError` — base for every storage error.
- :class:`PersistenceError` — base for the at-rest crypto, secret store,
  blob store, envelope, file lock, path containment, and audit-redaction
  surfaces. Subclass of :class:`StorageError` so existing catchers
  continue to work.
"""

from __future__ import annotations

from ..errors import AeatError


class StorageError(AeatError):
    """Base class for every error raised by :mod:`aeat.storage`."""


class MigrationError(StorageError):
    """Raised when an Alembic migration operation fails."""


class RepositoryError(StorageError):
    """Raised when a repository operation fails (not-found, integrity, etc.)."""


class PersistenceError(StorageError):
    """Base class for governed-persistence error subtypes.

    Errors raised by the at-rest crypto primitives, the secret store, the
    encrypted blob store, the schema-version envelope, the file-lock helper,
    the path containment helper, and the audit-sink redaction contract all
    inherit from this class.
    """


class EncryptionError(PersistenceError):
    """Base class for AEAD encryption / decryption failures."""


class DecryptionError(EncryptionError):
    """Raised when AEAD decryption fails (tag mismatch, malformed input)."""


class KeyDerivationError(EncryptionError):
    """Raised when an HKDF / scrypt key-derivation step fails."""


class NonceCollisionError(EncryptionError):
    """Raised on a defensive nonce-uniqueness invariant violation."""


class SecretStoreError(PersistenceError):
    """Base class for secret-store I/O failures."""


class KeyringUnavailableError(SecretStoreError):
    """Raised when the OS keychain backend is unusable.

    Either no backend is registered (e.g. headless Linux without
    libsecret), the backend rejected the operation, or the configured
    backend is the no-op ``null`` keyring.
    """


class MasterKeyUnavailableError(SecretStoreError):
    """Raised when no master key can be acquired from any provider."""


class LockAcquisitionError(PersistenceError):
    """Raised when an exclusive file lock cannot be acquired within the timeout."""


class ClassificationError(PersistenceError):
    """Raised when a record's declared sensitivity class is incompatible with its repository.

    Example: writing a CORPUS-class blob through the encrypted-blob path,
    or loading an envelope under a different classification than the
    one persisted on disk.
    """


class EnvelopeVersionError(PersistenceError):
    """Raised when an on-disk envelope is older or newer than the consumer expects.

    Older envelopes may be migrated forward via
    :func:`migrate_envelope`; newer envelopes are not safely
    consumable by older code and refuse to load.
    """


class PathContainmentError(PersistenceError, ValueError):
    """Raised when a computed path escapes its configured root directory.

    Inherits from :class:`ValueError` as well as :class:`PersistenceError` so
    legacy call-sites that catch ``ValueError`` from the path helpers in
    :mod:`aeat._paths` continue to work; new code should catch the
    typed :class:`PathContainmentError` instead.
    """


class BlobNotFoundError(PersistenceError):
    """Raised when a blob lookup misses on the encrypted blob store."""


class BlobIntegrityError(PersistenceError):
    """Raised when a blob's on-disk SHA-256 disagrees with its manifest."""
