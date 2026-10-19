"""Content hashes shared by native packaging operations.

:func:`digest` is the lowercase hex SHA-256 of a file's bytes. Inside
:func:`digest_cache` it reuses the digest it recorded for the same file while
the file's size, modification time and file identity are unchanged, and
records every digest it computes in ``<build>/cache/digests.json``, the one
digest cache every packaging step of that binary directory shares.

The cache never answers for a file it could not have seen change. A digest is
reused only when the file was last written well before it was hashed
(:data:`SETTLED_NS`): a later write then always moves the modification time,
however coarse the filesystem's clock, so a stale digest is never returned.

:func:`digest_cache` names the cache in :data:`CACHE_VARIABLE` for its
duration, so a child process started with this process's environment, such as
the producer a cached CMake action runs, uses the same cache without entering
the context itself; its entries are written back when it exits. A child that
is given an explicit environment uses the cache only if that environment keeps
the variable. Concurrent processes merge their entries under a lock file, and
none drops another's.
"""

from __future__ import annotations

import atexit
import contextlib
import hashlib
import json
import os
import threading
import time
from collections.abc import Generator
from pathlib import Path
from typing import Final

CACHE_VARIABLE: Final = "CADRUMO_NATIVE_DIGEST_CACHE"
"""Names the digest cache file a packaging process and its children share."""
SETTLED_NS: Final = 5 * 1_000_000_000
"""How long before it was hashed a file must have last been written for its digest to be reused."""
_SCHEMA: Final = 1
_LOCK_ATTEMPTS: Final = 6000
_STALE_LOCK_SECONDS: Final = 30.0


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _merge(current: dict[str, list[int | str]], other: dict[str, list[int | str]]) -> None:
    """Keep, for each path, the entry hashed last."""
    for name, entry in other.items():
        held = current.get(name)
        if held is None or int(held[3]) <= int(entry[3]):
            current[name] = entry


class _Cache:
    """One process's view of a shared digest cache file."""

    def __init__(self, file: Path) -> None:
        self.file = file
        self.entries: dict[str, list[int | str]] = {}
        self.recorded: dict[str, list[int | str]] = {}
        self.guard = threading.Lock()
        self.entries.update(self._read())

    def _read(self) -> dict[str, list[int | str]]:
        try:
            document = json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(document, dict) or document.get("schema") != _SCHEMA:
            return {}
        entries = document.get("entries")
        if not isinstance(entries, dict):
            return {}
        # An entry of any other shape is not trusted, only hashed again.
        return {
            str(name): [*entry]
            for name, entry in entries.items()
            if isinstance(entry, list)
            and len(entry) == 5
            and all(isinstance(value, int) for value in entry[:4])
            and isinstance(entry[4], str)
        }

    def digest(self, path: Path) -> str:
        name = os.path.normcase(os.path.abspath(path))
        status = os.stat(path)
        key = [status.st_size, status.st_mtime_ns, status.st_ino]
        with self.guard:
            entry = self.entries.get(name)
        if entry is not None and entry[:3] == key and int(entry[1]) < int(entry[3]) - SETTLED_NS:
            return str(entry[4])
        hashed = time.time_ns()
        value = _hash(path)
        after = os.stat(path)
        # Written while it was read: the digest names no single version of the file.
        if [after.st_size, after.st_mtime_ns, after.st_ino] == key:
            with self.guard:
                self.entries[name] = self.recorded[name] = [*key, hashed, value]
        return value

    @contextlib.contextmanager
    def _locked(self) -> Generator[None]:
        lock = self.file.with_name(self.file.name + ".lock")
        for _ in range(_LOCK_ATTEMPTS):
            try:
                descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                # A holder that died leaves its lock; one older than any flush is not held.
                with contextlib.suppress(OSError):
                    if time.time() - lock.stat().st_mtime > _STALE_LOCK_SECONDS:
                        lock.unlink()
                time.sleep(0.01)
                continue
            try:
                yield
            finally:
                os.close(descriptor)
                lock.unlink(missing_ok=True)
            return
        raise TimeoutError(f"The digest cache lock {lock} stayed held")

    def flush(self) -> None:
        """Merge this process's new entries into the shared file, keeping every other process's."""
        with self.guard:
            recorded, self.recorded = self.recorded, {}
        if not recorded:
            return
        self.file.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            merged = self._read()
            _merge(merged, recorded)
            temporary = self.file.with_name(f"{self.file.name}.{os.getpid()}.tmp")
            temporary.write_text(json.dumps({"schema": _SCHEMA, "entries": merged}), encoding="utf-8")
            os.replace(temporary, self.file)


_active: _Cache | None = None
_inherited: _Cache | None = None


def _current() -> _Cache | None:
    global _inherited
    if _active is not None:
        return _active
    named = os.environ.get(CACHE_VARIABLE)
    if named is None or named == "":
        return None
    if _inherited is None or _inherited.file != Path(named):
        _inherited = _Cache(Path(named))
        atexit.register(_inherited.flush)
    return _inherited


def digest(path: Path) -> str:
    """Hash one build input or delivered file: the lowercase hex SHA-256 of its bytes."""
    cache = _current()
    return _hash(path) if cache is None else cache.digest(path)


@contextlib.contextmanager
def digest_cache(build: Path) -> Generator[Path]:
    """Share the digest cache of binary directory ``build`` with this process and the children it starts."""
    global _active
    file = Path(build).absolute() / "cache" / "digests.json"
    outer, previous = _active, os.environ.get(CACHE_VARIABLE)
    _active = _Cache(file)
    os.environ[CACHE_VARIABLE] = str(file)
    try:
        yield file
    finally:
        try:
            _active.flush()
        finally:
            _active = outer
            if previous is None:
                os.environ.pop(CACHE_VARIABLE, None)
            else:
                os.environ[CACHE_VARIABLE] = previous
