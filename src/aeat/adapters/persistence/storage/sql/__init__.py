"""SQL substrate: ORM, engine, session, repositories, records, and schema setup.

Public surface for the SQLAlchemy-backed relational storage components.
Re-exports the engine factory (:func:`create_engine_from_settings`,
:func:`get_engine`, :func:`dispose_engine`), session helpers
(:func:`get_sessionmaker`, :func:`session_scope`), the Alembic upgrade
entry point (:func:`upgrade_to_head`), public pydantic record models
(:class:`ModeloRecord`, :class:`PortalRecord`, :class:`PortalAuthMethod`,
:class:`CorpusArtifactRecord`), and the per-domain repositories
(:class:`Repository`, :class:`ModeloRepository`, :class:`PortalRepository`,
:class:`CorpusArtifactRepository`).
"""

from __future__ import annotations

from .engine import create_engine_from_settings, dispose_engine, get_engine
from .migrations_api import upgrade_to_head
from .records import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord
from .repository import (
    CorpusArtifactRepository,
    ModeloRepository,
    PortalRepository,
    Repository,
)
from .secure_objects import SecureObjectMetadata, SecureObjectRecord, SecureObjectRepository
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
    "create_engine_from_settings",
    "dispose_engine",
    "get_engine",
    "get_sessionmaker",
    "session_scope",
    "upgrade_to_head",
]
