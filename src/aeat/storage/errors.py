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
