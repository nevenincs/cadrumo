"""SQL substrate: ORM, engine, session, repositories, records, migrations.

Public surface for the SQLAlchemy-backed relational storage cluster.
Bucket boundary established by audit-4 in the aeat-restructure ADR.
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
