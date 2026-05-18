"""SQL substrate: ORM, engine, session, repositories, records, and schema setup.

Public surface for the SQLAlchemy-backed relational storage components.
Re-exports the engine factory (:func:`create_engine_from_settings`,
:func:`get_engine`, :func:`dispose_engine`), session helpers
(:func:`get_sessionmaker`, :func:`session_scope`), public pydantic record models
(:class:`ModeloRecord`, :class:`PortalRecord`, :class:`PortalAuthMethod`,
:class:`CorpusArtifactRecord`), and the per-domain repositories
(:class:`Repository`, :class:`ModeloRepository`, :class:`PortalRepository`,
:class:`CorpusArtifactRepository`).

Schema is materialised from the ORM metadata on first engine access; the
codebase is forward-only and carries no migration history.
"""

from __future__ import annotations

from .engine import create_engine_from_settings, dispose_engine, get_engine
from .records import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord
from .repository import (
    CorpusArtifactRepository,
    ModeloRepository,
    PortalRepository,
    Repository,
)
from .secure_objects import SecureObjectMetadata, SecureObjectRecord, SecureObjectRepository, SecureObjectWrite
from .session import get_sessionmaker, session_scope

__all__ = [
    "CorpusArtifactRecord",
    "CorpusArtifactRepository",
    "ModeloRecord",
    "ModeloRepository",
    "PortalAuthMethod",
    "PortalRecord",
    "PortalRepository",
    "Repository",
    "SecureObjectMetadata",
    "SecureObjectRecord",
    "SecureObjectRepository",
    "SecureObjectWrite",
    "create_engine_from_settings",
    "dispose_engine",
    "get_engine",
    "get_sessionmaker",
    "session_scope",
]
