"""Session and unit-of-work helpers for the SQL persistence layer.

Thin wrappers around :class:`sqlalchemy.orm.sessionmaker` that enforce
commit-on-success and rollback-on-exception semantics via a context
manager. Pairs with :func:`adapters.persistence.storage.sql.engine.get_engine`
to provide a default binding when callers do not pass an explicit
engine.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .....core.logging import get_logger
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
def session_scope(engine: Engine | None = None) -> Generator[Session]:
    """Context-managed unit of work.

    Commits on normal exit, rolls back on exception, and always closes the
    session.

    Args:
        engine: Optional engine override. When ``None``, :func:`get_engine`
            is consulted.

    Yields:
        A live :class:`~sqlalchemy.orm.Session`.

    Raises:
        Exception: Re-raised after rolling back when the session body raises.
    """
    factory = get_sessionmaker(engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:  # rollback on any error then re-raise; SQLAlchemy exception surface is too broad to enumerate
        _log.debug("session_scope rolling back due to exception", exc_info=True)
        session.rollback()
        raise
    finally:
        session.close()
