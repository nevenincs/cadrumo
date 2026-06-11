"""SQL substrate: ORM, engine, session, repositories, records, and schema setup.

Public surface for the SQLAlchemy-backed relational storage components.
Re-exports the engine factory (:func:`create_engine_from_settings`,
:func:`get_engine`, :func:`dispose_engine`), session helpers
(:func:`get_sessionmaker`, :func:`session_scope`), public pydantic record models
(:class:`ModeloCatalogueRecord`, :class:`PortalRecord`, :class:`PortalAuthMethod`,
:class:`CorpusArtifactRecord`), and the per-domain repositories
(:class:`SqlRecordRepository`, :class:`ModeloRepository`, :class:`PortalRepository`,
:class:`CorpusArtifactRepository`), and the encrypted key-value store
:class:`SecureObjectRepository`.

Schema is materialised from the ORM metadata on first engine access; the
codebase is forward-only and carries no migration history.
"""

from __future__ import annotations

from .engine import create_engine_from_settings, dispose_engine, get_engine
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
    SecureObjectNamespaceIntegrity,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectWrite,
)
from .session import get_sessionmaker, session_scope

__all__ = [
    "CorpusArtifactRecord",
    "CorpusArtifactRepository",
    "ModeloCatalogueRecord",
    "ModeloRepository",
    "PortalAuthMethod",
    "PortalRecord",
    "PortalRepository",
    "SecureObjectDecryptabilityRow",
    "SecureObjectMetadata",
    "SecureObjectNamespaceIntegrity",
    "SecureObjectRecord",
    "SecureObjectRepository",
    "SecureObjectWrite",
    "SqlRecordRepository",
    "create_engine_from_settings",
    "dispose_engine",
    "get_engine",
    "get_sessionmaker",
    "session_scope",
]
