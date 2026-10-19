"""Content hashes shared by native packaging operations.

:func:`digest` is the lowercase hex SHA-256 of a file's bytes. Inside
:func:`digest_cache` it reuses the digest it recorded for the same file while
the file's size, modification time and file identity are unchanged, and
records every digest it computes in ``<build>/cache/digests.sqlite``, the one
digest cache every packaging step of that binary directory shares. A lookup
reads one row; nothing loads the whole cache.

The cache never answers for a file it could not have seen change. A digest is
reused only when the file was last written well before it was hashed
(:data:`SETTLED_NS`): a later write then always moves the modification time,
however coarse the filesystem's clock, so a stale digest is never returned.
A file that changed while it was read is not recorded.

:func:`digest_cache` names the cache in :data:`CACHE_VARIABLE` for its
duration, so a child process started with this process's environment, such as
the producer a cached CMake action runs, uses the same cache without entering
the context itself; its entries are written when it exits. A child given an
explicit environment uses the cache only if that environment keeps the
variable. A process that recorded nothing writes nothing. Concurrent processes
write row by row in SQLite transactions, and none drops another's rows; rows
for files that no longer exist are pruned about once a day.
"""

from __future__ import annotations

import atexit
import contextlib
import hashlib
import os
import sqlite3
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Final

CACHE_VARIABLE: Final = "CADRUMO_NATIVE_DIGEST_CACHE"
"""Names the digest cache database a packaging process and its children share."""
SETTLED_NS: Final = 5 * 1_000_000_000
"""How long before it was hashed a file must have last been written for its digest to be reused."""
PRUNE_INTERVAL_NS: Final = 24 * 3600 * 1_000_000_000
"""How often rows for files that no longer exist are removed."""
_BUSY_MS: Final = 60_000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    path TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime INTEGER NOT NULL,
    ino INTEGER NOT NULL, hashed INTEGER NOT NULL, sha256 TEXT NOT NULL
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS meta (name TEXT PRIMARY KEY, value INTEGER NOT NULL) WITHOUT ROWID;
"""


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class _Cache:
    """One process's connection to a shared digest cache database."""

    def __init__(self, file: Path) -> None:
        self.file = file
        self.recorded: dict[str, tuple[int, int, int, int, str]] = {}
        self.guard = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    def _connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.file, timeout=_BUSY_MS / 1000, check_same_thread=False)
            connection.execute(f"PRAGMA busy_timeout = {_BUSY_MS}")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(_SCHEMA)
            self._connection = connection
        return self._connection

    def _lookup(self, name: str) -> tuple[int, int, int, int, str] | None:
        recorded = self.recorded.get(name)
        if recorded is not None:
            return recorded
        try:
            row = (
                self._connect()
                .execute("SELECT size, mtime, ino, hashed, sha256 FROM entries WHERE path = ?", (name,))
                .fetchone()
            )
        except sqlite3.Error:
            return None
        return None if row is None else (int(row[0]), int(row[1]), int(row[2]), int(row[3]), str(row[4]))

    def digest(self, path: Path) -> str:
        name = os.path.normcase(os.path.abspath(path))
        status = os.stat(path)
        key = (status.st_size, status.st_mtime_ns, status.st_ino)
        with self.guard:
            entry = self._lookup(name)
        if entry is not None and entry[:3] == key and entry[1] < entry[3] - SETTLED_NS:
            return entry[4]
        hashed = time.time_ns()
        value = _hash(path)
        after = os.stat(path)
        # Written while it was read: the digest names no single version of the file.
        if (after.st_size, after.st_mtime_ns, after.st_ino) == key:
            with self.guard:
                self.recorded[name] = (*key, hashed, value)
        return value

    def flush(self) -> None:
        """Write this process's new rows, keeping the newest row per path; nothing when none is new."""
        with self.guard:
            recorded, self.recorded = self.recorded, {}
            if not recorded:
                return
            connection = self._connect()
            with connection:
                connection.executemany(
                    "INSERT INTO entries (path, size, mtime, ino, hashed, sha256) VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(path) DO UPDATE SET size = excluded.size, mtime = excluded.mtime, "
                    "ino = excluded.ino, hashed = excluded.hashed, sha256 = excluded.sha256 "
                    "WHERE excluded.hashed >= entries.hashed",
                    [(name, *entry) for name, entry in recorded.items()],
                )
            self._prune(connection)

    def _prune(self, connection: sqlite3.Connection) -> None:
        now = time.time_ns()
        row = connection.execute("SELECT value FROM meta WHERE name = 'pruned'").fetchone()
        if row is not None and now - int(row[0]) < PRUNE_INTERVAL_NS:
            return
        gone = [(name,) for (name,) in connection.execute("SELECT path FROM entries") if not os.path.isfile(name)]
        with connection:
            connection.executemany("DELETE FROM entries WHERE path = ?", gone)
            connection.execute(
                "INSERT INTO meta (name, value) VALUES ('pruned', ?) "
                "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
                (now,),
            )

    def close(self) -> None:
        with self.guard:
            if self._connection is not None:
                self._connection.close()
                self._connection = None


_active: _Cache | None = None
_inherited: _Cache | None = None


def _finish(cache: _Cache) -> None:
    try:
        cache.flush()
    finally:
        cache.close()


def _current() -> _Cache | None:
    global _inherited
    if _active is not None:
        return _active
    named = os.environ.get(CACHE_VARIABLE)
    if named is None or named == "":
        return None
    if _inherited is None or _inherited.file != Path(named):
        _inherited = _Cache(Path(named))
        atexit.register(_finish, _inherited)
    return _inherited


def digest(path: Path) -> str:
    """Hash one build input or delivered file: the lowercase hex SHA-256 of its bytes."""
    cache = _current()
    return _hash(path) if cache is None else cache.digest(path)


@contextlib.contextmanager
def digest_cache(build: Path) -> Generator[Path]:
    """Share the digest cache of binary directory ``build`` with this process and the children it starts."""
    global _active
    file = Path(build).absolute() / "cache" / "digests.sqlite"
    # The cache's earlier single-file form, which every process rewrote whole.
    with contextlib.suppress(OSError):
        (file.parent / "digests.json").unlink(missing_ok=True)
    outer, previous = _active, os.environ.get(CACHE_VARIABLE)
    _active = _Cache(file)
    os.environ[CACHE_VARIABLE] = str(file)
    try:
        yield file
    finally:
        try:
            _finish(_active)
        finally:
            _active = outer
            if previous is None:
                os.environ.pop(CACHE_VARIABLE, None)
            else:
                os.environ[CACHE_VARIABLE] = previous
