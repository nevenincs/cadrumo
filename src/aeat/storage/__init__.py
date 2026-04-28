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
from ._corpus_manifest import (
    CorpusEntry,
    CorpusManifest,
    CorpusManifestDiff,
    assert_corpus_clean,
    build_corpus_manifest,
    load_corpus_manifest,
    manifest_path_for,
    save_corpus_manifest,
    verify_corpus_manifest,
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
    AeadAlgorithm,
    CipherEnvelope,
    EncryptionMetadata,
    Envelope,
    EnvelopeMigrator,
    load_encrypted_envelope,
    load_envelope,
    reencrypt_envelope_file,
    save_encrypted_envelope,
    save_envelope,
)
from ._lock import DEFAULT_LOCK_TIMEOUT, exclusive_file_lock
from ._master_key import (
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    MigrationResult,
    get_master_key_provider,
    migrate_master_key_kdf,
)
from ._materialisation import (
    export_to_temp_path,
    get_secret_store,
    materialise_secret,
    override_secret_store,
)
from ._path_safety import safe_record_path, safe_repository_id, safe_subpath
from ._redaction import (
    default_rules,
    default_rules_for,
    default_rules_for_class,
    redact,
    redact_structured,
)
from ._rotation import (
    RotationPlanEntry,
    RotationSummary,
    default_blob_store_roots,
    default_rotation_plan,
    rotate_blob_stores,
    rotate_master_key,
)
from ._secret_store import SecretRecord, SecretStore
from .engine import create_engine_from_settings, dispose_engine, get_engine
from .errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    ClassificationError,
    CorpusManifestDriftError,
    CorpusManifestError,
    CorpusManifestTamperError,
    DecryptionError,
    EncryptionError,
    EnvelopeVersionError,
    KeyDerivationError,
    KeyringUnavailableError,
    LockAcquisitionError,
    MasterKeyKdfVersionError,
    MasterKeyUnavailableError,
    MigrationError,
    NonceCollisionError,
    PathContainmentError,
    PersistenceError,
    RepositoryError,
    RetentionPolicyError,
    SecretAlreadyExistsError,
    SecretNotFoundError,
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
    "AeadAlgorithm",
    "AtRestTreatment",
    "BlobIntegrityError",
    "BlobManifest",
    "BlobNotFoundError",
    "BlobReference",
    "CipherEnvelope",
    "ClassificationError",
    "ClassificationPolicy",
    "CorpusArtifactRecord",
    "CorpusArtifactRepository",
    "CorpusEntry",
    "CorpusManifest",
    "CorpusManifestDiff",
    "CorpusManifestDriftError",
    "CorpusManifestError",
    "CorpusManifestTamperError",
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
    "MasterKeyKdfVersionError",
    "MasterKeyProvider",
    "MasterKeyUnavailableError",
    "MigrationError",
    "MigrationResult",
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
    "RetentionPolicyError",
    "RotationPlanEntry",
    "RotationSummary",
    "SecretAlreadyExistsError",
    "SecretNotFoundError",
    "SecretRecord",
    "SecretStore",
    "SecretStoreError",
    "SensitivityClass",
    "StorageError",
    "assert_corpus_clean",
    "build_corpus_manifest",
    "create_engine_from_settings",
    "decrypt_record",
    "default_blob_store_roots",
    "default_policy_for",
    "default_policy_table",
    "default_rotation_plan",
    "default_rules",
    "default_rules_for",
    "default_rules_for_class",
    "derive_key",
    "dispose_engine",
    "downgrade_to_base",
    "encrypt_record",
    "exclusive_file_lock",
    "export_to_temp_path",
    "get_engine",
    "get_master_key_provider",
    "get_secret_store",
    "get_sessionmaker",
    "load_corpus_manifest",
    "load_encrypted_envelope",
    "load_envelope",
    "manifest_path_for",
    "materialise_secret",
    "migrate_master_key_kdf",
    "override_master_key_provider",
    "override_secret_store",
    "redact",
    "redact_structured",
    "reencrypt_envelope_file",
    "rotate_blob_stores",
    "rotate_master_key",
    "round_trip_migrations",
    "safe_record_path",
    "safe_repository_id",
    "safe_subpath",
    "save_corpus_manifest",
    "save_encrypted_envelope",
    "save_envelope",
    "session_scope",
    "upgrade_to_head",
    "verify_corpus_manifest",
]
