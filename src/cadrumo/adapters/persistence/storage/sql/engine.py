"""SQLAlchemy engine factory for the storage subpackage.

Provides a lazy singleton engine cache used by the rest of
:mod:`adapters.persistence.storage`. Bucket-routed engines are cached
under their bucket identity (resolved storage root plus bucket id) so that
engine lifetime can follow the bucket-session lifecycle; the database URL
is an implementation detail of engine construction. Explicit database URLs
and the root-fallback database keep their URL-keyed direct path. The
factory normalises SQLite URLs against
the application data root, ensures the parent directory exists,
and attaches a ``connect`` listener that configures each SQLite
connection: ``foreign_keys=ON`` (cascade enforcement) and a
``busy_timeout`` (so concurrent invocations on one bucket no longer fail
immediately with "database is locked").

Disposal is an internal seam of the engine lifecycle owner: the bucket
session (``BucketSession.close``) disposes via :func:`dispose_engine_handle`
and :func:`dispose_engines_for_bucket`, the bucket-destruction path uses
:func:`dispose_engines_for_bucket` to release file handles before removing
a bucket directory, and test-harness teardown uses :func:`dispose_engine`.
Production code outside those owners must not dispose engines directly.
"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.pool import ConnectionPoolEntry

from .....core.config import (
    FORMER_PRODUCT_DATABASE_FILENAME,
    Settings,
    StorageRouteKind,
    classify_storage_route,
    load_settings,
)
from .....core.external_constants import UTF_8_ENCODING
from .....core.hashing import sha256_hex
from .....core.logging import get_logger
from .....core.paths import resolve_project_path
from ..errors import StorageError
from ..storage_path_definitions import BUCKETS_DIRNAME

_log = get_logger(__name__)
# Cache key axes: ("bucket", <resolved storage root>, <bucket id>) for
# active-bucket routes, ("url", "", <database url>) for explicit-URL and
# root-fallback routes.
_EngineCacheKey = tuple[str, str, str]
_engines: dict[_EngineCacheKey, Engine] = {}
_lock = Lock()

# A writer that finds the bucket DB locked by a concurrent connection waits up to
# this long for the lock to clear instead of failing immediately with
# ``SQLITE_BUSY`` ("database is locked"). Five seconds comfortably covers the
# brief windows a single-row secure-object write holds the write lock.
_SQLITE_BUSY_TIMEOUT_MS = 5000


def _route_marker(url: str) -> str:
    """Return a stable non-reversible marker for a configured database route."""
    return sha256_hex(url.encode(UTF_8_ENCODING))[:16]


def _normalize_sqlite_url(url: str) -> str:
    """Anchor relative SQLite database files to the application data root.

    Args:
        url: SQLAlchemy URL. No-op for non-SQLite URLs and in-memory databases.

    Returns:
        The original ``url`` for non-SQLite or in-memory targets, otherwise an
        equivalent URL whose database path has been resolved through
        :func:`core.paths.resolve_project_path`.
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


def _refuse_absent_bucket_root(parent: Path) -> None:
    """Refuse to bring a bucket root into existence while opening an engine.

    A bucket root under ``buckets/`` is created exactly once, by the
    no-replace rename that publishes its profile capsule. Creating one here
    as a side effect of resolving a database path would be a second bucket
    creator: it enrols an empty directory that carries no capsule, and the
    real publication then finds its destination occupied and refuses.

    Args:
        parent: The directory that would hold the SQLite database file.

    Raises:
        StorageError: When the bucket root the database sits under is absent.
    """
    for ancestor in (parent, *parent.parents):
        if ancestor.parent.name != BUCKETS_DIRNAME or os.path.lexists(ancestor):
            continue
        raise StorageError(
            "refusing to create a bucket directory while opening a database engine; "
            "a bucket exists only once its profile capsule is published.",
            context={"bucket_directory": str(ancestor)},
            translated_message="errors.storage.engine.create_failed",
        )


def _ensure_sqlite_parent(url: str) -> None:
    """Create the parent directory of a SQLite database file if needed.

    Directories are created only within an already-published bucket; see
    :func:`_refuse_absent_bucket_root` for why the bucket root itself is
    never created here.

    Args:
        url: A SQLAlchemy URL. No-op for non-SQLite URLs and ``:memory:``.
    """
    parsed = make_url(_normalize_sqlite_url(url))
    database = parsed.database
    if database and database != ":memory:":
        parent = Path(database).parent
        _refuse_absent_bucket_root(parent)
        parent.mkdir(parents=True, exist_ok=True)


def _refuse_former_product_database_target(url: str) -> None:
    """Refuse an explicit SQLite target using the retired product filename."""
    parsed = make_url(url)
    database = parsed.database
    if not parsed.drivername.startswith("sqlite") or not database or database == ":memory:":
        return
    if Path(database).name != FORMER_PRODUCT_DATABASE_FILENAME:
        return
    raise StorageError(
        "refusing retired product database filename; configure a Cadrumo database target.",
        context={"route_marker": _route_marker(url)},
        translated_message="errors.storage.engine.create_failed",
    )


def _attach_sqlite_pragmas(engine: Engine) -> None:
    """Attach a ``connect`` listener that configures the SQLite bucket database.

    Every new connection issues two pragmas (no-ops for non-SQLite dialects,
    harmless for ``:memory:`` databases):

    - ``foreign_keys=ON`` so ``ON DELETE CASCADE`` / ``SET NULL`` declared in the
      schema are enforced (SQLite ignores them otherwise).
    - ``busy_timeout`` so a writer that meets a held lock from a concurrent
      ``aeat`` invocation on the same bucket waits its turn rather than failing
      immediately with ``SQLITE_BUSY`` ("database is locked").
    - ``journal_mode=WAL`` so readers do not block the writer and the writer does
      not block readers — the right concurrency model for the many-concurrent-
      ``aeat``-invocation workload. WAL keeps committed pages in a ``-wal``
      sidecar until a checkpoint folds them into the main database file, so any
      at-rest plaintext scan over the raw file must read the ``-wal`` sidecar too
      (see ``read_db_at_rest_bytes`` in the shared test surface). A no-op on
      ``:memory:`` databases, which have no on-disk journal.
    - ``synchronous=NORMAL`` — the durability level WAL is designed for: it cannot
      corrupt the database, and at most loses the last transaction on an OS/power
      crash (acceptable for a build-and-export local store; never used for live
      AEAT submission).

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
            cursor.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")  # nosem
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        finally:
            cursor.close()


def create_engine_from_settings(settings: Settings) -> Engine:
    """Create a fresh SQLAlchemy :class:`~sqlalchemy.engine.Engine` from settings.

    When the engine targets SQLite, a ``connect`` listener enables
    ``PRAGMA foreign_keys=ON`` on every new connection so that
    ``ON DELETE CASCADE`` / ``SET NULL`` constraints declared in the schema
    are enforced at runtime.

    Args:
        settings: Application :class:`~core.config.Settings` carrying
            ``cadrumo_database_url``.

    Returns:
        A new SQLAlchemy :class:`~sqlalchemy.engine.Engine`.

    Raises:
        StorageError: When the configured URL is empty or cannot be parsed.
    """
    url = settings.cadrumo_database_url
    if not url:
        raise StorageError(
            "configured database URL is empty.",
            translated_message="errors.storage.engine.empty_database_url",
        )
    try:
        normalized_url = _normalize_sqlite_url(url)
        _refuse_former_product_database_target(normalized_url)
        _ensure_sqlite_parent(normalized_url)
        engine = create_engine(normalized_url, future=True)
    except StorageError:
        raise
    except Exception as exc:
        raise StorageError(
            "failed to create storage engine.",
            context={"route_marker": _route_marker(url), "error_type": type(exc).__name__},
            translated_message="errors.storage.engine.create_failed",
        ) from exc
    _attach_sqlite_pragmas(engine)
    _log.debug("created engine route_marker=%s", _route_marker(url))
    return engine


def _engine_cache_key(settings: Settings) -> _EngineCacheKey:
    """Return the cache key for ``settings``: bucket identity when bucket-routed.

    Active-bucket routes key on the resolved storage root plus bucket id so
    the same bucket resolves the same engine regardless of how the URL was
    spelled; explicit database URLs and the root-fallback database keep the
    URL itself as the key (the settings-driven direct path).
    """
    route = classify_storage_route(settings)
    if route.kind is StorageRouteKind.ACTIVE_BUCKET_DATABASE and route.bucket_id:
        root = str(settings.cadrumo_local_storage_root.expanduser().resolve())
        return ("bucket", root, route.bucket_id)
    return ("url", "", settings.cadrumo_database_url)


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a process-wide singleton engine, keyed by bucket identity.

    Bucket-routed settings cache the engine under (storage root, bucket id);
    explicit-URL and root-fallback settings cache under the database URL.
    On first access, materialises every ORM table declared on
    :class:`~adapters.persistence.storage.sql._orm.Base.metadata`
    against the new engine. The codebase is forward-only: there is no
    migration history; the schema is whatever the current ORM defines.

    Args:
        settings: Optional :class:`~core.config.Settings` override.
            When ``None``, a fresh :func:`core.config.load_settings`
            call is used.

    Returns:
        The cached :class:`~sqlalchemy.engine.Engine` for the resolved
        route, creating it on first access.
    """
    resolved = settings or load_settings()
    key = _engine_cache_key(resolved)
    with _lock:
        cached = _engines.get(key)
        if cached is not None:
            return cached
        engine = create_engine_from_settings(resolved)
        from .orm import Base

        Base.metadata.create_all(engine)
        _engines[key] = engine
        return engine


def dispose_engine(settings: Settings | None = None) -> None:
    """Dispose and forget the cached engine for the given settings.

    Internal lifecycle seam: invoked by the session owner
    (``BucketSession.close`` via the handle/bucket-scoped variants below)
    and by test-harness teardown. Production code must not call it —
    engine disposal is owned by the bucket-session lifecycle.

    Args:
        settings: Optional :class:`~core.config.Settings` override.
            When ``None``, every cached engine is disposed.
    """
    with _lock:
        if settings is None:
            for engine in _engines.values():
                engine.dispose()
            _engines.clear()
            return
        engine = _engines.pop(_engine_cache_key(settings), None)
        if engine is not None:
            engine.dispose()


def dispose_engines_for_bucket(bucket_id: str) -> None:
    """Dispose and forget every cached engine bound to ``bucket_id``.

    The bucket-scoped disposal seam: the session owner
    (``BucketSession.close``) sweeps its bucket's engines on close/switch,
    and the bucket-destruction path releases the bucket's SQLite file
    handles before removing the bucket directory (an open handle blocks
    the rename on Windows). Engines cached for other buckets and for
    explicit database URLs are untouched.
    """
    with _lock:
        keys = tuple(key for key in _engines if key[0] == "bucket" and key[2] == bucket_id)
        for key in keys:
            _engines.pop(key).dispose()


def dispose_engine_handle(engine: Engine) -> None:
    """Dispose ``engine`` and evict it from the cache by identity.

    Session-owner seam for engine handles registered on a
    ``BucketSession`` at first storage access: disposal targets exactly
    the registered engine, regardless of which route key cached it.
    """
    with _lock:
        for key, cached in _engines.items():
            if cached is engine:
                del _engines[key]
                break
    engine.dispose()
