"""Unit-of-work helper for the SQL persistence layer.

A context manager that opens one Core :class:`~sqlalchemy.engine.Connection`,
runs its body inside one transaction, commits on success and rolls back on
exception. Pairs with :func:`adapters.persistence.storage.sql.engine.get_engine`
to provide a default binding when callers do not pass an explicit engine.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine

from .....core.logging import get_logger
from .engine import get_engine

_log = get_logger(__name__)


@contextmanager
def session_scope(engine: Engine | None = None, *, serializable: bool = False) -> Generator[Connection]:
    """Context-managed unit of work over one connection and one transaction.

    Commits on normal exit, rolls back on exception, and always returns the
    connection to the pool.

    Args:
        engine: Optional engine override. When ``None``, :func:`get_engine`
            is consulted.
        serializable: Protect read predicates through commit. SQLite acquires
            its write reservation before any reads, including absent-row checks;
            other backends must support SQLAlchemy's SERIALIZABLE isolation.

    Yields:
        A live :class:`~sqlalchemy.engine.Connection` inside its transaction.

    Raises:
        Exception: Re-raised after rolling back when the body raises.
    """
    with (engine or get_engine()).connect() as connection:
        transaction = None
        try:
            if serializable:
                connection.execution_options(isolation_level="SERIALIZABLE")
            transaction = connection.begin()
            if serializable and connection.dialect.name == "sqlite":
                # sqlite3's legacy transaction mode does not BEGIN on SELECT.
                # Reserve the writer before observing source revisions so a
                # concurrent insert cannot invalidate an absence assertion.
                connection.exec_driver_sql("BEGIN IMMEDIATE")
            yield connection
            transaction.commit()
        except Exception:  # rollback on any error then re-raise; SQLAlchemy exception surface is too broad to enumerate
            _log.debug("session_scope rolling back due to exception", exc_info=True)
            if transaction is not None:
                transaction.rollback()
            raise
