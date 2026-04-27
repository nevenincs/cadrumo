"""Persistence layer and migrations entry point.

Public API of the storage subpackage. Callers outside :mod:`aeat.storage` MUST
import only from here — internal modules (``_orm``, ``engine``, ``session``,
``repository``, ``migrations_api``) are implementation details.

The public surface is intentionally narrow:

- Pydantic v2 record models: :class:`ModeloRecord`, :class:`PortalRecord`,
  :class:`CorpusArtifactRecord`, plus :class:`PortalAuthMethod`.
- Errors: :class:`StorageError`, :class:`MigrationError`,
  :class:`RepositoryError`.
- Engine + session helpers: :func:`get_engine`, :func:`dispose_engine`,
  :func:`session_scope`.
- Typed repositories: :class:`ModeloRepository`, :class:`PortalRepository`,
  :class:`CorpusArtifactRepository`.
- Migration helpers: :func:`upgrade_to_head`, :func:`downgrade_to_base`,
  :func:`round_trip_migrations`.

See the evolution workflow section of the data-storage ADR
(``.vault/adr/2026-04-12-data-storage-adr.md``) for how to add columns and
write migrations.
"""

from __future__ import annotations

from ._blob_store import (
    BlobManifest,
    BlobReference,
    EncryptedBlobStore,
)
from ._classification import (
    AtRestTreatment,
    ClassificationPolicy,
    RedactionRule,
    RedactionStrategy,
    RetentionPolicy,
    SensitivityClass,
    default_policy_for,
    default_policy_table,
)
from ._crypto import (
    GCM_TAG_SIZE,
    KEY_SIZE,
    NONCE_SIZE,
    EncryptedBlob,
    decrypt_record,
    derive_key,
    encrypt_record,
)
from ._encrypted_columns import (
    EncryptedBytes,
    EncryptedJSON,
    EncryptedString,
    HashedLookup,
    override_master_key_provider,
)
from ._envelope import (
    EncryptionMetadata,
    Envelope,
    EnvelopeMigrator,
    load_envelope,
    save_envelope,
)
from ._lock import DEFAULT_LOCK_TIMEOUT, exclusive_file_lock
from ._master_key import (
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    get_master_key_provider,
)
from ._path_safety import safe_record_path, safe_subpath
from ._redaction import (
    default_rules,
    default_rules_for,
    default_rules_for_class,
    redact,
)
from .engine import create_engine_from_settings, dispose_engine, get_engine
from .errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    ClassificationError,
    DecryptionError,
    EncryptionError,
    EnvelopeVersionError,
    KeyDerivationError,
    KeyringUnavailableError,
    LockAcquisitionError,
    MasterKeyUnavailableError,
    MigrationError,
    NonceCollisionError,
    PathContainmentError,
    PersistenceError,
    RepositoryError,
    SecretStoreError,
    StorageError,
)
from .migrations_api import downgrade_to_base, round_trip_migrations, upgrade_to_head
from .records import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord
from .repository import CorpusArtifactRepository, ModeloRepository, PortalRepository, Repository
from .session import get_sessionmaker, session_scope

__all__ = [
    "DEFAULT_LOCK_TIMEOUT",
    "GCM_TAG_SIZE",
    "KEY_SIZE",
    "NONCE_SIZE",
    "AtRestTreatment",
    "BlobIntegrityError",
    "BlobManifest",
    "BlobNotFoundError",
    "BlobReference",
    "ClassificationError",
    "ClassificationPolicy",
    "CorpusArtifactRecord",
    "CorpusArtifactRepository",
    "DecryptionError",
    "EncryptedBlob",
    "EncryptedBlobStore",
    "EncryptedBytes",
    "EncryptedJSON",
    "EncryptedString",
    "EncryptionError",
    "EncryptionMetadata",
    "Envelope",
    "EnvelopeMigrator",
    "EnvelopeVersionError",
    "EphemeralMasterKeyProvider",
    "FileFallbackMasterKeyProvider",
    "HashedLookup",
    "KeyDerivationError",
    "KeyringMasterKeyProvider",
    "KeyringUnavailableError",
    "LockAcquisitionError",
    "MasterKeyProvider",
    "MasterKeyUnavailableError",
    "MigrationError",
    "ModeloRecord",
    "ModeloRepository",
    "NonceCollisionError",
    "PathContainmentError",
    "PersistenceError",
    "PortalAuthMethod",
    "PortalRecord",
    "PortalRepository",
    "RedactionRule",
    "RedactionStrategy",
    "Repository",
    "RepositoryError",
    "RetentionPolicy",
    "SecretStoreError",
    "SensitivityClass",
    "StorageError",
    "create_engine_from_settings",
    "decrypt_record",
    "default_policy_for",
    "default_policy_table",
    "default_rules",
    "default_rules_for",
    "default_rules_for_class",
    "derive_key",
    "dispose_engine",
    "downgrade_to_base",
    "encrypt_record",
    "exclusive_file_lock",
    "get_engine",
    "get_master_key_provider",
    "get_sessionmaker",
    "load_envelope",
    "override_master_key_provider",
    "redact",
    "round_trip_migrations",
    "safe_record_path",
    "safe_subpath",
    "save_envelope",
    "session_scope",
    "upgrade_to_head",
]
