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
from .engine import create_engine_from_settings, dispose_engine, get_engine
from .errors import MigrationError, RepositoryError, StorageError
from .migrations_api import downgrade_to_base, round_trip_migrations, upgrade_to_head
from .records import CorpusArtifactRecord, ModeloRecord, PortalAuthMethod, PortalRecord
from .repository import CorpusArtifactRepository, ModeloRepository, PortalRepository, Repository
from .session import get_sessionmaker, session_scope

__all__ = [
    "AtRestTreatment",
    "ClassificationPolicy",
    "CorpusArtifactRecord",
    "CorpusArtifactRepository",
    "MigrationError",
    "ModeloRecord",
    "ModeloRepository",
    "PortalAuthMethod",
    "PortalRecord",
    "PortalRepository",
    "RedactionRule",
    "RedactionStrategy",
    "Repository",
    "RepositoryError",
    "RetentionPolicy",
    "SensitivityClass",
    "StorageError",
    "create_engine_from_settings",
    "default_policy_for",
    "default_policy_table",
    "dispose_engine",
    "downgrade_to_base",
    "get_engine",
    "get_sessionmaker",
    "round_trip_migrations",
    "session_scope",
    "upgrade_to_head",
]
