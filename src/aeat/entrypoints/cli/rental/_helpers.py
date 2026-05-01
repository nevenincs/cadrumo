"""Shared helpers for the ``aeat rental`` Typer sub-app.

Storage imports are deferred behind :func:`open_session` so the sub-app
does not pull :mod:`aeat.adapters.persistence.storage` (with its alembic
plugin discovery) into every CLI command's import chain; this preserves
the JSON-pipe-safety contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — type-only imports
    from sqlalchemy.orm import Session


@contextmanager
def open_session() -> Iterator[Session]:
    """Yield a SQLAlchemy :class:`Session` bound to the configured database.

    Each invocation creates a fresh engine and disposes it on exit so
    the CLI does not retain DB connections beyond a single command. The
    configured ``aeat_database_url`` on :class:`aeat.core.config.Settings`
    is used; the default is a local SQLite database under ``var/aeat.db``.

    Yields:
        An open :class:`sqlalchemy.orm.Session` scoped to one CLI
        invocation.
    """
    from ....adapters.persistence.storage import create_engine_from_settings, session_scope
    from ....core.config import load_settings

    settings = load_settings()
    engine = create_engine_from_settings(settings)
    try:
        with session_scope(engine) as session:
            yield session
    finally:
        engine.dispose()


__all__ = ["open_session"]
