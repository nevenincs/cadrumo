"""Persistence layer and migrations entry point.

Public API of the storage subpackage. Callers outside
:mod:`aeat.adapters.persistence.storage` must import only from here; internal
modules (``sql._orm``, ``sql.engine``, ``sql.session``, ``sql.repository``,
and the encryption substrate under ``crypto``,
``envelope``, ``master_key``, ``blob_store``, ``secret_store``) are
implementation details.

The phrase **encryption substrate** denotes the layered crypto stack
(master-key provider → envelope wrapper → encrypted blob store →
typed column helpers) that every persisted record passes through.
Throughout the package, "substrate" without a qualifier refers to
this stack.

The public surface is intentionally narrow:

- Pydantic v2 record models — :class:`ModeloRecord`, :class:`PortalRecord`,
  :class:`CorpusArtifactRecord`, plus :class:`PortalAuthMethod`.
- Errors — :class:`StorageError`, :class:`RepositoryError`.
- Engine and session helpers — :func:`get_engine`, :func:`dispose_engine`,
  :func:`session_scope`.
- Typed repositories — :class:`ModeloRepository`, :class:`PortalRepository`,
  :class:`CorpusArtifactRepository`.
- Encryption substrate — :class:`Envelope`, :class:`EncryptedBlobStore`,
  :class:`MasterKeyProvider`, :class:`SecretStore`, plus the column-level
  helpers :class:`EncryptedString`, :class:`EncryptedBytes`,
  :class:`EncryptedJSON`, and :class:`HashedLookup`.
"""

from __future__ import annotations

from ....core.classification import (
    AtRestTreatment,
    ClassificationPolicy,
    RedactionRule,
    RedactionStrategy,
    RetentionPolicy,
    SensitivityClass,
    default_policy_for,
    default_policy_table,
)
from ....core.corpus_manifest import (
    CorpusEntry,
    CorpusManifest,
    CorpusManifestDiff,
    CorpusManifestDriftError,
    CorpusManifestError,
    CorpusManifestTamperError,
    assert_corpus_clean,
    build_corpus_manifest,
    load_corpus_manifest,
    manifest_path_for,
    save_corpus_manifest,
    verify_corpus_manifest,
)
from ....core.locks import DEFAULT_LOCK_TIMEOUT, exclusive_file_lock
from ....core.locks_errors import LockAcquisitionError
from ....core.redaction import (
    default_rules,
    default_rules_for,
    default_rules_for_class,
    redact,
    redact_for_log,
    redact_structured,
)
from ._path_safety import safe_record_path, safe_repository_id, safe_subpath
from ._rotation import (
    RotationPlanEntry,
    RotationSummary,
    default_blob_store_roots,
    default_rotation_plan,
    rotate_blob_stores,
    rotate_master_key,
)
from .blob_store._blob_store import (
    BlobManifest,
    BlobReference,
    EncryptedBlobStore,
)
from .blob_store._materialisation import (
    export_to_temp_path,
    get_secret_store,
    materialise_secret,
    override_secret_store,
)
from .crypto._crypto import (
    GCM_TAG_SIZE,
    KEY_SIZE,
    NONCE_SIZE,
    EncryptedBlob,
    decrypt_record,
    derive_key,
    encrypt_record,
)
from .crypto._encrypted_columns import (
    EncryptedBytes,
    EncryptedJSON,
    EncryptedString,
    HashedLookup,
)
from .master_key._active_session import (
    NoActiveBucketSessionError,
    activate_session,
    get_active_master_key,
)
from .envelope._envelope import (
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
from .errors import (
    BlobIntegrityError,
    BlobNotFoundError,
    ClassificationError,
    DecryptionError,
    EncryptionError,
    EnvelopeVersionError,
    KeyDerivationError,
    KeyringUnavailableError,
    MasterKeyKdfVersionError,
    MasterKeyKeychainLockedError,
    MasterKeyMaterialMissingError,
    MasterKeyPassphraseMismatchError,
    MasterKeyUnavailableError,
    NonceCollisionError,
    PathContainmentError,
    PersistenceError,
    RepositoryError,
    RetentionPolicyError,
    SecretAlreadyExistsError,
    SecretNotFoundError,
    SecretStoreError,
    StorageError,
    StorageValidationError,
    UnsecuredModeRefusedError,
)
from .master_key._master_key import (
    EphemeralMasterKeyProvider,
    FileFallbackMasterKeyProvider,
    KeyringMasterKeyProvider,
    MasterKeyProvider,
    UnsecuredMasterKeyProvider,
    atomic_write_secure_bytes,
    get_master_key_provider,
    looks_like_real_tax_id,
    refuse_unsecured_with_real_nif,
)
from .master_key._recovery import (
    RecoveryKey,
    WrappedMasterKey,
    decode_mnemonic,
    encode_mnemonic,
    generate_recovery_key,
    load_wrapped_master_key,
    save_wrapped_master_key,
    unwrap_master_key,
    wrap_master_key,
)
from .secret_store._secret_store import SecretRecord, SecretStore
from .sql.engine import create_engine_from_settings, dispose_engine, get_engine
from .sql.records import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord
from .sql.repository import CorpusArtifactRepository, ModeloRepository, PortalRepository, Repository
from .sql.session import get_sessionmaker, session_scope

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
    "MasterKeyKeychainLockedError",
    "MasterKeyMaterialMissingError",
    "MasterKeyPassphraseMismatchError",
    "MasterKeyProvider",
    "MasterKeyUnavailableError",
    "ModeloRecord",
    "ModeloRepository",
    "NonceCollisionError",
    "PathContainmentError",
    "PersistenceError",
    "PortalAuthMethod",
    "PortalRecord",
    "PortalRepository",
    "RecoveryKey",
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
    "StorageValidationError",
    "UnsecuredMasterKeyProvider",
    "UnsecuredModeRefusedError",
    "WrappedMasterKey",
    "assert_corpus_clean",
    "atomic_write_secure_bytes",
    "build_corpus_manifest",
    "create_engine_from_settings",
    "decode_mnemonic",
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
    "encode_mnemonic",
    "encrypt_record",
    "exclusive_file_lock",
    "export_to_temp_path",
    "generate_recovery_key",
    "get_engine",
    "get_master_key_provider",
    "get_secret_store",
    "get_sessionmaker",
    "load_corpus_manifest",
    "load_encrypted_envelope",
    "load_envelope",
    "load_wrapped_master_key",
    "looks_like_real_tax_id",
    "manifest_path_for",
    "materialise_secret",
    "NoActiveBucketSessionError",
    "activate_session",
    "get_active_master_key",
    "override_secret_store",
    "redact",
    "redact_for_log",
    "redact_structured",
    "reencrypt_envelope_file",
    "refuse_unsecured_with_real_nif",
    "rotate_blob_stores",
    "rotate_master_key",
    "safe_record_path",
    "safe_repository_id",
    "safe_subpath",
    "save_corpus_manifest",
    "save_encrypted_envelope",
    "save_envelope",
    "save_wrapped_master_key",
    "session_scope",
    "unwrap_master_key",
    "verify_corpus_manifest",
    "wrap_master_key",
]
