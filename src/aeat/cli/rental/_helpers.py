"""Shared helpers for the ``aeat rental`` sub-app (#454)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from ...config import load_settings
from ...storage import create_engine_from_settings, session_scope


@contextmanager
def open_session() -> Iterator[Session]:
    """Open a SQLAlchemy session bound to the configured database.

    Each invocation creates a fresh engine and disposes it on exit
    so the CLI does not retain DB connections beyond a single
    command. The configured ``aeat_database_url`` from
    :class:`Settings` is used; defaults to a local SQLite database
    under ``var/aeat.db``.
    """
    settings = load_settings()
    engine = create_engine_from_settings(settings)
    try:
        with session_scope(engine) as session:
            yield session
    finally:
        engine.dispose()


__all__ = ["open_session"]
