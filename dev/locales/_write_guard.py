"""Serialised, conflict-detecting access to the shared locale catalogues.

Every catalogue edit is a read-modify-write: parse ~3 MB of YAML, mutate one
leaf, write the whole file back. Two of those overlapping is a lost update --
both read the same base, both write, and the first writer's change disappears
with no error and no gate signal. Inter-locale parity checks key *presence*, so
a lost value edit silently restores stale operator-facing prose while every gate
stays green. That has already happened in this repository.

Atomicity does not address this. An atomic write guarantees no reader ever sees
a torn file; it says nothing about two complete writes racing, and the loser's
change is just as gone.

Two failure sources need covering, and this module closes each with the
mechanism that actually fits it:

- **Concurrent CLI writers.** A PID-stamped ``O_EXCL`` lockfile beside the
  catalogues serialises the whole read-modify-write, not just the write, so a
  second writer reads the first one's result rather than racing it. A holder
  that died leaves a lock reclaimed on the next attempt via
  :func:`~cadrumo.core.pid_is_alive`.

- **Writers that never took the lock** -- a hand edit, an editor save, a bulk
  sweep. No lock can exclude those, so :class:`CatalogueWriteGuard` digests each
  file as it is read and refuses the write if the bytes moved underneath. The
  refusal is a :class:`~dev.locales.errors.LocaleWriteConflictError`, telling the
  operator to retry rather than silently clobbering.

The lock alone would leave the second class unguarded; the digest check alone
would only narrow the first, because two writers can both pass the check before
either replaces the file. Together they close both, and neither adds a second
write path: every write still lands through
:func:`~cadrumo.core.atomic_write.atomic_write_text`.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from cadrumo.core import LOCKFILE_UNLINK_RETRY_SECONDS, pid_is_alive, unlink_lockfile
from cadrumo.core.atomic_write import atomic_write_text
from cadrumo.core.external_constants import UTF_8_ENCODING
from cadrumo.core.logging import get_logger

from .errors import LocaleError, LocaleWriteConflictError

_log = get_logger(__name__)

LOCK_FILENAME = ".catalogue-write.lock"
"""Name of the lockfile serialising catalogue writers, beside the catalogues."""

_DEFAULT_WAIT_SECONDS = 60.0
_POLL_SECONDS = 0.02
_ABSENT_DIGEST = ""


def _digest_bytes(raw: bytes) -> str:
    """Return the content fingerprint used to detect an out-of-band write."""
    return hashlib.sha256(raw).hexdigest()


def _digest_path(path: Path) -> str:
    """Fingerprint ``path``, distinguishing an absent file from an empty one."""
    try:
        return _digest_bytes(path.read_bytes())
    except FileNotFoundError:
        return _ABSENT_DIGEST


def _decode_universal_newlines(raw: bytes) -> str:
    r"""Decode ``raw`` exactly as :meth:`Path.read_text` would.

    The line-oriented leaf writers rebuild a catalogue from
    ``splitlines(keepends=True)``, so their output depends on whether the
    decoded text still carries ``\\r\\n``. ``read_text`` runs in universal-newline
    mode and collapses them; reproducing that here keeps the written bytes
    identical while letting the caller fingerprint the raw bytes it read.
    """
    return raw.decode(UTF_8_ENCODING).replace("\r\n", "\n").replace("\r", "\n")


class CatalogueWriteGuard:
    """Pairs every catalogue read with the write that supersedes it.

    A write is refused unless the file still carries the bytes this guard saw
    when it first read the file. Writing a path this guard never read is a
    contributor error, not a conflict: it means a write path bypassed the guard,
    which is the defect the guard exists to prevent.
    """

    def __init__(self) -> None:
        self._observed: dict[Path, str] = {}

    def read_text(self, path: Path) -> str:
        """Read ``path`` and record the bytes this edit is based on.

        Re-reading a path already observed keeps the *first* fingerprint: the
        conflict question is whether the file moved since the edit began, and
        the line-oriented writers legitimately re-read the file they are about
        to rewrite.
        """
        raw = path.read_bytes()
        self._observed.setdefault(path.resolve(), _digest_bytes(raw))
        return _decode_universal_newlines(raw)

    def observe(self, path: Path) -> None:
        """Record ``path``'s current bytes without reading its content.

        For a caller that parses the file through another reader (the strict
        YAML loader, the allowlist JSON decoder) but must still be held to the
        same conflict check.
        """
        self._observed.setdefault(path.resolve(), _digest_path(path))

    def write_text(self, path: Path, text: str) -> None:
        """Atomically write ``text`` unless ``path`` changed since it was read.

        Raises:
            LocaleWriteConflictError: When ``path`` no longer carries the bytes this
                guard read, meaning another writer landed a change that this
                write would silently discard.
            LocaleError: When ``path`` was never read through this guard.
        """
        key = path.resolve()
        expected = self._observed.get(key)
        if expected is None:
            raise LocaleError(
                f"Refusing to write {path.name}: it was not read through the catalogue write guard. "
                "Every catalogue write must be paired with the read it is based on."
            )
        if _digest_path(path) != expected:
            raise LocaleWriteConflictError(
                f"{path.name} changed while this edit was in flight; the edit was not written. "
                "Another writer or a hand edit landed first. Re-run the command to apply it on top."
            )
        atomic_write_text(path, text, encoding=UTF_8_ENCODING)
        self._observed[key] = _digest_bytes(text.encode(UTF_8_ENCODING))


@contextmanager
def catalogue_write_guard(
    locales_dir: Path,
    *,
    wait_seconds: float = _DEFAULT_WAIT_SECONDS,
) -> Generator[CatalogueWriteGuard]:
    """Hold the catalogue write lock for one read-modify-write cycle.

    Args:
        locales_dir: Directory holding the catalogues and the lockfile.
        wait_seconds: How long to wait for a peer writer before refusing.

    Yields:
        The guard every read and write inside the cycle must go through.

    Raises:
        LocaleError: When the lock is still held after ``wait_seconds``.
    """
    lock = locales_dir / LOCK_FILENAME
    _acquire(lock, wait_seconds=wait_seconds)
    try:
        yield CatalogueWriteGuard()
    finally:
        _release(lock)


def _try_create(lock: Path) -> bool:
    """Atomically create ``lock`` stamped with this PID, or report it held.

    A ``PermissionError`` counts as held rather than propagating: on Windows a
    lockfile whose delete is still pending, or one a peer has open to read the
    holder PID, refuses the open with ``ERROR_ACCESS_DENIED``. Both clear on
    their own, so the caller should keep polling.
    """
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    flags |= getattr(os, "O_NOINHERIT", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(lock, flags, 0o600)
    except (FileExistsError, PermissionError):
        return False
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
    finally:
        os.close(descriptor)
    return True


def _read_holder(lock: Path) -> int | None:
    """Return the PID stamped in ``lock``, or ``None`` when it cannot be read."""
    try:
        raw = lock.read_bytes().decode("ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    return int(raw) if raw.isdigit() else None


def _reclaim_if_stale(lock: Path) -> None:
    """Remove ``lock`` when the process that stamped it is gone.

    Every uncertainty resolves to "held": an unreadable stamp, a stamp this
    process cannot parse, or a holder whose liveness cannot be determined all
    leave the lock in place. Wrongly reclaiming a live lock admits the second
    writer this module exists to exclude, which is strictly worse than waiting.
    """
    holder = _read_holder(lock)
    if holder is None or pid_is_alive(holder):
        return
    # Re-read immediately before unlinking and reclaim only when the stamp is
    # unchanged. Without it, a peer that reclaimed this same stale lock and
    # stamped its own live PID in between would have its lock deleted here,
    # letting a third writer in.
    if _read_holder(lock) != holder:
        _log.debug("locale catalogue lock reclaim aborted; holder changed under reclaim")
        return
    _log.debug("reclaiming locale catalogue lock stamped with dead pid=%s", holder)
    # Best effort: a peer reclaiming the same stale lock, or reading its stamp,
    # can block the unlink briefly. Losing the race just means another poll.
    unlink_lockfile(lock, reason="stale_reclaim")


def _acquire(lock: Path, *, wait_seconds: float) -> None:
    """Take the catalogue lock, waiting out a live peer up to ``wait_seconds``."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    while True:
        if _try_create(lock):
            return
        _reclaim_if_stale(lock)
        if _try_create(lock):
            return
        if time.monotonic() >= deadline:
            holder = _read_holder(lock)
            raise LocaleError(
                f"Timed out after {wait_seconds:g}s waiting for the locale catalogue lock at {lock} "
                f"(held by pid {holder if holder is not None else 'unknown'}). "
                "Another catalogue edit is still running; retry once it finishes."
            )
        time.sleep(_POLL_SECONDS)


def _release(lock: Path) -> None:
    """Drop the catalogue lock, never removing one stamped by another process.

    The removal goes through :func:`~cadrumo.core.unlink_lockfile`, the shared
    primitive the bucket and auth-acquisition locks use for the same reason:
    Windows refuses to delete a file while any handle is open, and every waiting
    writer opens the lockfile to read its holder PID. Failing to release would
    be worse than slow: the stamped holder is this live process, so no peer
    would ever reclaim the lock as stale and every later writer would block
    until its own timeout.

    Raises:
        LocaleError: When the lock could not be removed within the retry window.
    """
    if _read_holder(lock) != os.getpid():
        _log.debug("locale catalogue lock not released; it is no longer stamped with this pid")
        return
    if unlink_lockfile(lock, retry_seconds=LOCKFILE_UNLINK_RETRY_SECONDS, reason="release"):
        return
    raise LocaleError(
        f"Could not release the locale catalogue lock at {lock} within "
        f"{LOCKFILE_UNLINK_RETRY_SECONDS:g}s. Delete it by hand once no catalogue edit is running."
    )


__all__ = ["LOCK_FILENAME", "CatalogueWriteGuard", "catalogue_write_guard"]
