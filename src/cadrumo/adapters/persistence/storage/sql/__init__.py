"""SQL substrate: ORM, engine, sessions, repositories, and secure objects.

Public surface for the SQLAlchemy-backed relational storage components.
Re-exports the engine factory (:func:`create_engine_from_settings`,
:func:`get_engine`, :func:`dispose_engine`), session helpers
(:func:`get_sessionmaker`, :func:`session_scope`), public pydantic record models
(:class:`ModeloCatalogueRecord`, :class:`PortalRecord`, :class:`PortalAuthMethod`,
:class:`CorpusArtifactRecord`), and the per-domain repositories
(:class:`SqlRecordRepository`, :class:`ModeloRepository`, :class:`PortalRepository`,
:class:`CorpusArtifactRepository`), and the encrypted key-value store
:class:`SecureObjectRepository`.

The secure-object surface also exports :class:`SecureObjectRecord`,
:class:`SecureObjectWrite`, :class:`SecureObjectDeletion`,
:class:`SecureObjectMetadata`, :class:`SecureObjectNamespaceIntegrity`,
:class:`SecureObjectDecryptabilityRow`, and
:func:`verify_revision_self_consistency` — the revision-lineage
self-consistency gate the decrypting read path applies before decryption, for
callers that need the same check against rows read through a path that
bypasses column decryption (e.g. :meth:`SecureObjectRepository.iter_all_records_raw`).
The repository stores payloads as
AES-GCM encrypted bytes, stores natural keys through
:class:`adapters.persistence.storage.HashedLookup`, binds row identity
into AEAD associated data, and gates reads by sensitivity class and schema
version. Listing defaults fail closed on unreadable rows; explicit diagnostic
APIs return typed decryptability metadata without plaintext disclosure.

Schema is materialised from the ORM metadata on first engine access. Runtime
route ownership stays in the storage-runtime and repository-factory modules;
this package facade only re-exports the SQL storage API.
"""

from __future__ import annotations

from ._orm import Base, FincaRow, SecureObjectRow, TransactionDateIndexRow
from ._secure_object_crypto import verify_revision_self_consistency
from ._secure_object_records import SecureObjectDeletion
from ._secure_object_schema import ensure_quarantine_table
from .engine import (
    create_engine_from_settings,
    dispose_engine,
    dispose_engine_handle,
    dispose_engines_for_bucket,
    get_engine,
)
from .records import CorpusArtifactRecord, ModeloCatalogueRecord, PortalAuthMethod, PortalRecord
from .repository import (
    CorpusArtifactRepository,
    ModeloRepository,
    PortalRepository,
    SqlRecordRepository,
)
from .secure_objects import (
    SecureObjectDecryptabilityRow,
    SecureObjectMetadata,
    SecureObjectMigrationTarget,
    SecureObjectNamespaceIntegrity,
    SecureObjectRawRow,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectWrite,
)
from .session import get_sessionmaker, session_scope

__all__ = [
    "Base",
    "CorpusArtifactRecord",
    "CorpusArtifactRepository",
    "FincaRow",
    "ModeloCatalogueRecord",
    "ModeloRepository",
    "PortalAuthMethod",
    "PortalRecord",
    "PortalRepository",
    "SecureObjectDecryptabilityRow",
    "SecureObjectDeletion",
    "SecureObjectMetadata",
    "SecureObjectMigrationTarget",
    "SecureObjectNamespaceIntegrity",
    "SecureObjectRawRow",
    "SecureObjectRecord",
    "SecureObjectRepository",
    "SecureObjectRow",
    "SecureObjectWrite",
    "SqlRecordRepository",
    "TransactionDateIndexRow",
    "create_engine_from_settings",
    "dispose_engine",
    "dispose_engine_handle",
    "dispose_engines_for_bucket",
    "ensure_quarantine_table",
    "get_engine",
    "get_sessionmaker",
    "session_scope",
    "verify_revision_self_consistency",
]
