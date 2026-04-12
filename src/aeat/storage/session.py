"""Session / unit-of-work helpers.

Thin wrappers around :class:`sqlalchemy.orm.sessionmaker` that enforce
commit-on-success / rollback-on-exception semantics via a context manager.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from aeat.logging import get_logger

from .engine import get_engine

_log = get_logger(__name__)


def get_sessionmaker(engine: Engine | None = None) -> sessionmaker[Session]:
    """Return a :class:`~sqlalchemy.orm.sessionmaker` bound to ``engine``.

    Args:
        engine: Optional engine override. When ``None``, :func:`get_engine`
            is consulted.

    Returns:
        A configured :class:`sessionmaker` instance.
    """
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Context-managed unit of work.

    Commits on normal exit, rolls back on exception, and always closes the
    session.

    Args:
        engine: Optional engine override. When ``None``, :func:`get_engine`
            is consulted.

    Yields:
        A live :class:`~sqlalchemy.orm.Session`.
    """
    factory = get_sessionmaker(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        _log.debug("session_scope rolling back due to exception")
        session.rollback()
        raise
    finally:
        session.close()
