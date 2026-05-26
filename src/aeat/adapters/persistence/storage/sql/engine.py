"""SQLAlchemy engine factory for the storage subpackage.

Provides a lazy, URL-keyed singleton engine used by the rest of
:mod:`aeat.adapters.persistence.storage`. The factory normalises SQLite
URLs against :data:`aeat.core.paths.PROJECT_ROOT`, ensures the parent
directory exists, and attaches a ``connect`` listener that enables
``PRAGMA foreign_keys=ON`` so cascade rules declared in the schema are
enforced at runtime.

Tests can dispose the cached engines between runs via
:func:`dispose_engine`.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.pool import ConnectionPoolEntry

from .....core.config import Settings, load_settings
from .....core.logging import get_logger
from .....core.paths import resolve_project_path
from ..errors import StorageError

_log = get_logger(__name__)
_engines: dict[str, Engine] = {}
_lock = Lock()


def _normalize_sqlite_url(url: str) -> str:
    """Anchor relative SQLite database files to ``PROJECT_ROOT``.

    Args:
        url: SQLAlchemy URL. No-op for non-SQLite URLs and in-memory databases.

    Returns:
        The original ``url`` for non-SQLite or in-memory targets, otherwise an
        equivalent URL whose database path has been resolved through
        :func:`aeat.core.paths.resolve_project_path`.
    """
    parsed = make_url(url)
    if not parsed.drivername.startswith("sqlite"):
        return url
    database = parsed.database
    if not database or database == ":memory:":
        return url
    resolved_db = resolve_project_path(database)
    normalized = URL.create(
        drivername=parsed.drivername,
        username=parsed.username,
        password=parsed.password,
        host=parsed.host,
        port=parsed.port,
        database=str(resolved_db),
        query=parsed.query,
    )
    return normalized.render_as_string(hide_password=False)


def _ensure_sqlite_parent(url: str) -> None:
    """Create the parent directory of a SQLite database file if needed.

    Args:
        url: A SQLAlchemy URL. No-op for non-SQLite URLs and ``:memory:``.
    """

    parsed = make_url(_normalize_sqlite_url(url))
    database = parsed.database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    """Attach a ``connect`` listener that enables SQLite foreign-key enforcement.

    SQLite ignores ``ON DELETE CASCADE`` and ``ON DELETE SET NULL`` unless
    ``PRAGMA foreign_keys=ON`` is issued on every new connection. This is a
    no-op for non-SQLite dialects.

    Args:
        engine: :class:`~sqlalchemy.engine.Engine` to attach the listener to.
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
    """Create a fresh SQLAlchemy :class:`~sqlalchemy.engine.Engine` from settings.

    When the engine targets SQLite, a ``connect`` listener enables
    ``PRAGMA foreign_keys=ON`` on every new connection so that
    ``ON DELETE CASCADE`` / ``SET NULL`` constraints declared in the schema
    are enforced at runtime.

    Args:
        settings: Application :class:`~aeat.core.config.Settings` carrying
            ``aeat_database_url``.

    Returns:
        A new SQLAlchemy :class:`~sqlalchemy.engine.Engine`.

    Raises:
        :exc:`aeat.adapters.persistence.storage.errors.StorageError`: If the
            configured URL is empty or cannot be parsed.
    """
    url = settings.aeat_database_url
    if not url:
        raise StorageError(
            "configured database URL is empty.",
            translated_message="errors.storage.engine.empty_database_url",
        )
    try:
        normalized_url = _normalize_sqlite_url(url)
        _ensure_sqlite_parent(normalized_url)
        engine = create_engine(normalized_url, future=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise StorageError(
            f"Failed to create engine for {url!r}: {exc}",
            translated_message="errors.storage.engine.create_failed",
        ) from exc
    _enable_sqlite_foreign_keys(engine)
    _log.debug("created engine for url=%s", url)
    return engine


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a process-wide singleton engine, keyed by database URL.

    On first access, materialises every ORM table declared on
    :class:`~aeat.adapters.persistence.storage.sql._orm.Base.metadata`
    against the new engine. The codebase is forward-only: there is no
    migration history; the schema is whatever the current ORM defines.

    Args:
        settings: Optional :class:`~aeat.core.config.Settings` override.
            When ``None``, a fresh :func:`aeat.core.config.load_settings`
            call is used.

    Returns:
        The cached :class:`~sqlalchemy.engine.Engine` for the resolved URL,
        creating it on first access.
    """
    resolved = settings or load_settings()
    url = resolved.aeat_database_url
    with _lock:
        cached = _engines.get(url)
        if cached is not None:
            return cached
        engine = create_engine_from_settings(resolved)
        from ._orm import Base

        Base.metadata.create_all(engine)
        _engines[url] = engine
        return engine


def dispose_engine(settings: Settings | None = None) -> None:
    """Dispose and forget the cached engine for the given settings.

    Args:
        settings: Optional :class:`~aeat.core.config.Settings` override.
            When ``None``, every cached engine is disposed.
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
