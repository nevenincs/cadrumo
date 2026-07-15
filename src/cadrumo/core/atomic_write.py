"""Shared two-tier atomic-write helper.

Every durable on-disk write in this codebase must never leave a torn or
partially-written file behind, whether the process crashes, is killed, or
raises mid-write. Before this module, four independent dialects of the same
"write a sibling tempfile, then :func:`os.replace` it over the target"
pattern had accreted across the storage substrate: a standard fsync+replace
variant (``adapters.persistence.storage.envelope``), a hidden-file variant
with no fsync, plain-write variants with no fsync at all, and a
collision-hardened ``O_EXCL`` + mode ``0o600`` variant reserved for the
master-key store. This module collapses all of that onto two named tiers
so a new writer picks one deliberately instead of inventing a fifth dialect:

- **Standard tier** (:func:`atomic_write_bytes`, :func:`atomic_write_text`):
  a :func:`tempfile.NamedTemporaryFile` sibling in the target's own parent
  directory (``{stem}.`` prefix, ``.tmp`` suffix), write, flush, ``fsync``,
  :func:`os.replace`, then a best-effort parent-directory ``fsync`` via
  :func:`~cadrumo.core.locks.fsync_parent_dir`. Suitable for ordinary durable
  application data with a single writer.

- **Hardened tier** (:func:`atomic_write_hardened_bytes`,
  :func:`atomic_write_hardened_text`): the master-key store's pattern --
  ``O_EXCL`` plus ``O_NOINHERIT``/``O_CLOEXEC`` where the platform defines
  them, file mode ``0o600``, and a collision-hardened
  ``{name}.{pid}.{token_hex}.tmp`` temp name -- before the same
  fsync/replace/parent-fsync sequence. Use this tier for secret-bearing
  targets or any target more than one process/thread could plausibly write
  concurrently; the ``O_EXCL`` open refuses to silently reuse or truncate an
  unexpected pre-existing tempfile. A memoryview-and-offset loop completes
  short :func:`os.write` calls and refuses a write that makes no progress.

Both tiers guarantee the tempfile is unlinked on ANY failure -- a bare
``try``/``finally`` around the whole sequence, not a narrow ``except
OSError`` -- so a ``KeyboardInterrupt`` or any other :class:`BaseException`
mid-write cannot leave an orphan tempfile next to the target. Neither tier
wraps or translates the underlying exception: callers see the raw
:class:`OSError` (or whatever the platform raises) so each call site can
apply its own domain-specific error class, matching the existing
call-site-owns-its-error-type convention this module's callers already use.
Payload content is never logged; only the target path and the exception
type are.

The helpers are freestanding primitives at the ``core`` layer with no
dependency beyond :func:`~cadrumo.core.locks.fsync_parent_dir`.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

from .locks import fsync_parent_dir
from .logging import get_logger

__all__ = [
    "atomic_write_bytes",
    "atomic_write_hardened_bytes",
    "atomic_write_hardened_text",
    "atomic_write_text",
]

_log = get_logger(__name__)

_HARDENED_DEFAULT_MODE = 0o600


def _write_all(fd: int, data: bytes) -> None:
    """Write ``data`` completely to an already-opened descriptor.

    Args:
        fd: Writable operating-system file descriptor.
        data: Byte payload to write in full.

    Raises:
        OSError: If the descriptor reports no forward progress or another
            operating-system write error occurs.
    """
    view = memoryview(data)
    offset = 0
    while offset < len(view):
        written = os.write(fd, view[offset:])
        if written <= 0:
            raise OSError("atomic byte write made no progress")
        offset += written


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically write ``data`` to ``path`` (standard tier).

    Stages a :func:`tempfile.NamedTemporaryFile` sibling in ``path``'s
    parent directory (created if absent), writes and fsyncs it, then
    replaces ``path`` with :func:`os.replace` and best-effort fsyncs
    the parent directory. The tempfile is unlinked on any failure, including
    a :class:`BaseException` raised mid-write.

    Args:
        path: Destination file. Parent directory is created if absent.
        data: Full file contents to write.

    Raises:
        OSError: When staging, writing, or replacing the file fails. The
            original exception propagates unwrapped; the tempfile is
            cleaned up first.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f"{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_and_fsync(tmp_path, path)
        tmp_path = None
    except BaseException as exc:
        _log.error(
            "atomic_write: standard-tier write failed target=%s error_type=%s",
            path,
            type(exc).__name__,
        )
        raise
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically write ``text`` to ``path`` (standard tier, text variant).

    Encodes ``text`` and delegates to :func:`atomic_write_bytes`; see its
    docstring for the write sequence and failure semantics.

    Args:
        path: Destination file. Parent directory is created if absent.
        text: Full file contents to write.
        encoding: Text encoding used to produce the bytes payload.
    """
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_hardened_bytes(path: Path, data: bytes, *, mode: int = _HARDENED_DEFAULT_MODE) -> None:
    """Atomically write ``data`` to ``path`` (hardened tier).

    Opens a collision-hardened ``{name}.{pid}.{token_hex}.tmp`` sibling with
    ``O_EXCL`` (refusing to reuse or truncate an unexpected pre-existing
    tempfile) plus ``O_NOINHERIT``/``O_CLOEXEC`` where the platform defines
    them, at file mode ``mode``. A memoryview-and-offset loop completes short
    :func:`os.write` calls and treats a non-positive write as an error. The
    staged bytes are fsynced before :func:`os.replace`, followed by a
    best-effort parent-directory fsync. The tempfile is unlinked on any
    failure, including a :class:`BaseException` raised mid-write. Use this tier
    for secret-bearing targets or targets more than one process could plausibly
    write concurrently.

    Args:
        path: Destination file. Parent directory is created if absent.
        data: Full file contents to write.
        mode: POSIX file mode for the staged tempfile (and, transitively,
            the replaced target). Defaults to ``0o600``.

    Raises:
        OSError: When staging, writing, or replacing the file fails
            (including ``FileExistsError`` from an ``O_EXCL`` collision).
            The original exception propagates unwrapped; the tempfile is
            cleaned up first.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOINHERIT", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    # O_BINARY is required on Windows: an fd opened without it is in text mode,
    # so os.write() translates every 0x0A byte to CRLF and silently corrupts
    # binary payloads (ciphertext, keys, PDFs) that contain a newline byte. The
    # flag is absent on POSIX, where getattr resolves to 0 (a no-op).
    flags |= getattr(os, "O_BINARY", 0)
    created = False
    try:
        fd = os.open(tmp_path, flags, mode)
        created = True
        try:
            _write_all(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        _replace_and_fsync(tmp_path, path)
        created = False
    except BaseException as exc:
        _log.error(
            "atomic_write: hardened-tier write failed target=%s error_type=%s",
            path,
            type(exc).__name__,
        )
        raise
    finally:
        if created:
            tmp_path.unlink(missing_ok=True)


def atomic_write_hardened_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    mode: int = _HARDENED_DEFAULT_MODE,
) -> None:
    """Atomically write ``text`` to ``path`` (hardened tier, text variant).

    Encodes ``text`` and delegates to :func:`atomic_write_hardened_bytes`;
    see its docstring for the write sequence and failure semantics.

    Args:
        path: Destination file. Parent directory is created if absent.
        text: Full file contents to write.
        encoding: Text encoding used to produce the bytes payload.
        mode: POSIX file mode for the staged tempfile. Defaults to ``0o600``.
    """
    atomic_write_hardened_bytes(path, text.encode(encoding), mode=mode)


def _replace_and_fsync(tmp_path: Path, target: Path) -> None:
    """Replace ``target`` with ``tmp_path`` and best-effort fsync its parent."""
    os.replace(tmp_path, target)
    fsync_parent_dir(target)
