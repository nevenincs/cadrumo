"""SQLAlchemy engine factory.

Provides a lazy, URL-keyed singleton engine used by the rest of the storage
subpackage. Tests can dispose the cached engines between runs via
:func:`dispose_engine`.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import ConnectionPoolEntry

from aeat.config import Settings, load_settings
from aeat.logging import get_logger

from .errors import StorageError

_log = get_logger(__name__)
_engines: dict[str, Engine] = {}
_lock = Lock()


def _ensure_sqlite_parent(url: str) -> None:
    """Create the parent directory of a SQLite database file if needed.

    Args:
        url: SQLAlchemy URL. No-op for non-SQLite URLs and in-memory databases.
    """
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite"):
        return
    database = parsed.database
    if not database or database == ":memory:":
        return
    db_path = Path(database)
    if not db_path.is_absolute():
        db_path = Path.cwd() / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Attach a ``connect`` listener that enables SQLite foreign-key enforcement.

    SQLite ignores ``ON DELETE CASCADE`` and ``ON DELETE SET NULL`` unless
    ``PRAGMA foreign_keys=ON`` is issued on every new connection. This is a
    no-op for non-SQLite dialects.

    Args:
        engine: Engine to attach the listener to.
    """
    if not engine.dialect.name.startswith("sqlite"):
        return

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def create_engine_from_settings(settings: Settings) -> Engine:
    """Create a fresh SQLAlchemy ``Engine`` from the given settings.

    When the engine targets SQLite, a ``connect`` listener enables
    ``PRAGMA foreign_keys=ON`` on every new connection so that
    ``ON DELETE CASCADE`` / ``SET NULL`` constraints declared in the schema
    are enforced at runtime.

    Args:
        settings: Application settings carrying ``aeat_database_url``.

    Returns:
        A new SQLAlchemy :class:`~sqlalchemy.engine.Engine`.

    Raises:
        StorageError: If the configured URL is empty or cannot be parsed.
    """
    url = settings.aeat_database_url
    if not url:
        raise StorageError("aeat_database_url is empty; set AEAT_DATABASE_URL.")
    try:
        _ensure_sqlite_parent(url)
        engine = create_engine(url, future=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise StorageError(f"Failed to create engine for {url!r}: {exc}") from exc
    _enable_sqlite_foreign_keys(engine)
    _log.debug("created engine for url=%s", url)
    return engine


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a process-wide singleton engine, keyed by database URL.

    Args:
        settings: Optional settings override. When ``None``, a fresh
            :func:`load_settings` call is used.

    Returns:
        The cached engine for the resolved URL, creating it on first access.
    """
    resolved = settings or load_settings()
    url = resolved.aeat_database_url
    with _lock:
        cached = _engines.get(url)
        if cached is not None:
            return cached
        engine = create_engine_from_settings(resolved)
        if resolved.aeat_storage_auto_migrate:
            # Imported lazily so `engine` stays free of an Alembic dependency
            # at module import time.
            from .migrations_api import upgrade_to_head

            _log.info("aeat_storage_auto_migrate=true; running alembic upgrade head")
            try:
                upgrade_to_head(engine)
            except Exception:
                engine.dispose()
                raise
        _engines[url] = engine
        return engine


def dispose_engine(settings: Settings | None = None) -> None:
    """Dispose and forget the cached engine for the given settings.

    Args:
        settings: Optional settings override. When ``None``, every cached
            engine is disposed.
    """
    with _lock:
        if settings is None:
            for engine in _engines.values():
                engine.dispose()
            _engines.clear()
            return
        url = settings.aeat_database_url
        engine = _engines.pop(url, None)
        if engine is not None:
            engine.dispose()
