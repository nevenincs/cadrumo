"""Shared SQLite engine bootstrap for secure-object repository tests.

Consolidated from four byte-identical copies across ``storage/sql/tests/``
and ``storage/envelope/tests/`` that had drifted apart only in the wrapping
contract around them (contextmanager vs plain function, self-managed vs
caller-supplied key provider, differing return shapes). This is the shared
plumbing those contracts wrap, not a unification of the contracts themselves.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine

from .....core.config import Settings
from ..sql import Base, create_engine_from_settings


def bootstrap_sqlite_engine(db_path: Path) -> Engine:
    """Create a real SQLite engine at ``db_path`` with the schema materialized."""

    engine = create_engine_from_settings(Settings(cadrumo_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine)
    return engine
