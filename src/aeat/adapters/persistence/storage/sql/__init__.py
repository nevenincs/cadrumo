"""SQL substrate: ORM, engine, session, repositories, records, and migrations.

Public surface for the SQLAlchemy-backed relational storage cluster.
Re-exports the engine factory (:func:`create_engine_from_settings`,
:func:`get_engine`, :func:`dispose_engine`), session helpers
(:func:`get_sessionmaker`, :func:`session_scope`), Alembic migration
entry points (:func:`upgrade_to_head`, :func:`downgrade_to_base`,
:func:`round_trip_migrations`), public pydantic record models
(:class:`ModeloRecord`, :class:`PortalRecord`, :class:`PortalAuthMethod`,
:class:`CorpusArtifactRecord`), and the per-domain repositories
(:class:`Repository`, :class:`ModeloRepository`, :class:`PortalRepository`,
:class:`CorpusArtifactRepository`).
"""

from __future__ import annotations

from .engine import create_engine_from_settings, dispose_engine, get_engine
from .migrations_api import downgrade_to_base, round_trip_migrations, upgrade_to_head
from .records import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord
from .repository import (
    CorpusArtifactRepository,
    ModeloRepository,
    PortalRepository,
    Repository,
)
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
    "create_engine_from_settings",
    "dispose_engine",
    "downgrade_to_base",
    "get_engine",
    "get_sessionmaker",
    "round_trip_migrations",
    "session_scope",
    "upgrade_to_head",
]
