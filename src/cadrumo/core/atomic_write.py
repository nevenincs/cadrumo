"""Shared two-tier atomic-write helper.

Every durable on-disk write in this codebase must never leave a torn or
partially-written file behind, whether the process crashes, is killed, or
raises mid-write. Before this module, four independent dialects of the same
"write a sibling tempfile, then :func:`os.replace` it over the target"
pattern had accreted across the storage substrate: a standard fsync+replace
variant (``adapters.persistence.storage.envelope``), a hidden-file variant
with no fsync, plain-write variants with no fsync at all, and a
collision-hardened ``O_EXCL`` + mode ``0o600`` variant reserved for the
master-key store. This module collapses all of that onto four named tiers
so a new writer picks one deliberately instead of inventing a fifth dialect:

- **Standard tier** (:func:`atomic_write_bytes`, :func:`atomic_write_text`):
  a :func:`tempfile.NamedTemporaryFile` sibling in
  the target's own parent directory (``{stem}.`` prefix, ``.tmp`` suffix),
  write, flush, ``fsync``, :func:`os.replace`, then a best-effort
  parent-directory ``fsync`` via :func:`~cadrumo.core.fsync.fsync_parent_dir`.
  Suitable for ordinary durable application data with a single writer.

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

- **Deferred-publish tier** (:func:`hardened_staged_publication`): the hardened
  tier's staging and publication with the write itself left to the caller, for
  a producer that cannot hand over a ``bytes`` payload -- it needs a real file
  on disk to build incrementally or to read back before the result becomes
  operator-visible, or it must complete unrelated work between the write and
  the publication. The staging sibling carries the same unguessable
  ``{name}.{pid}.{token_hex}.tmp`` name, the same ``O_EXCL`` reservation and
  the same ``0o600`` mode; publication is the same fsync/replace/parent-fsync
  sequence, requested explicitly so the caller can translate a publication
  failure into its own domain error. It exists because callers needing that
  shape were open-coding a predictable ``{name}.tmp`` sibling and a bare
  :func:`os.replace` next to the operator's chosen destination, which is a
  guessable name, an unsynced publication, and -- with a narrow ``except`` --
  a staged file that survives an interrupt.

- **Best-effort tier** (:func:`atomic_write_best_effort_bytes`,
  :func:`atomic_write_best_effort_text`): the same tempfile-sibling-plus-
  :func:`os.replace` mechanics as the standard tier, but deliberately WITHOUT
  any ``fsync`` call. Reserved for rebuildable derived caches (a compiled-
  registry pickle, a corpus-text extraction cache, a validation-verdict
  stamp) where a torn write on crash only costs a recompute on the next
  process, never data loss -- the fsync cost is not worth paying on a cache
  write. This tier never logs and never swallows: it raises the underlying
  exception unwrapped, same as the other two tiers, and leaves the
  try/except/log/swallow policy entirely to the caller, because every
  existing best-effort caller already wraps its write in its own catch with
  its own log level and message and duplicating that here would double-log
  or contradict it.

Every tier guarantees the tempfile is unlinked on ANY failure -- a bare
``try``/``finally`` around the whole sequence, not a narrow ``except
OSError`` -- so a ``KeyboardInterrupt`` or any other :class:`BaseException`
mid-write cannot leave an orphan tempfile next to the target. No tier wraps
or translates the underlying exception: callers see the raw
:class:`OSError` (or whatever the platform raises) so each call site can
apply its own domain-specific error class, matching the existing
call-site-owns-its-error-type convention this module's callers already use.
Payload content is never logged; only the target path and the exception
type are (the best-effort tier logs nothing at all; see above).

The helpers are freestanding primitives at the ``core`` layer with no
dependency beyond :func:`~cadrumo.core.fsync.fsync_parent_dir`.
"""

from __future__ import annotations

import os
import secrets
import stat
import sys
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from .descriptor_write import write_all
from .errors.hierarchy import InternalInvariantError
from .fsync import fsync_parent_dir
from .logging import get_logger

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes

__all__ = [
    "DurableWriteBatch",
    "StagedPublication",
    "atomic_write_best_effort_bytes",
    "atomic_write_best_effort_text",
    "atomic_write_bytes",
    "atomic_write_hardened_bytes",
    "atomic_write_hardened_text",
    "atomic_write_text",
    "hardened_staged_bytes_publication",
    "hardened_staged_publication",
]

_log = get_logger(__name__)

_HARDENED_DEFAULT_MODE = 0o600

if sys.platform == "win32":
    _WINDOWS_DELETE = 0x00010000
    _WINDOWS_FILE_READ_ATTRIBUTES = 0x00000080
    _WINDOWS_FILE_SHARE_ALL = 0x00000007
    _WINDOWS_OPEN_EXISTING = 3
    _WINDOWS_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _WINDOWS_FILE_ATTRIBUTE_TAG_INFO = 9
    _WINDOWS_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _WINDOWS_FILE_RENAME_INFO_EX = 22
    _WINDOWS_FILE_RENAME_REPLACE_IF_EXISTS = 0x00000001
    _WINDOWS_FILE_RENAME_POSIX_SEMANTICS = 0x00000002
    _WINDOWS_FILE_RENAME_INFO_EX_MINIMUM_BUILD = 14393
    _WINDOWS_ERROR_INVALID_FUNCTION = 1
    _WINDOWS_ERROR_NOT_SUPPORTED = 50
    _WINDOWS_INVALID_HANDLE = ctypes.c_void_p(-1).value

    class _WindowsFileAttributeTagInfo(ctypes.Structure):
        _fields_ = [("file_attributes", wintypes.DWORD), ("reparse_tag", wintypes.DWORD)]

    class _WindowsFileRenameInfoEx(ctypes.Structure):
        _fields_ = [
            ("flags", wintypes.DWORD),
            ("root_directory", wintypes.HANDLE),
            ("file_name_length", wintypes.DWORD),
            ("file_name", wintypes.WCHAR * 1),
        ]

    _WINDOWS_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _WINDOWS_CREATE_FILE = _WINDOWS_KERNEL32.CreateFileW
    _WINDOWS_CREATE_FILE.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _WINDOWS_CREATE_FILE.restype = wintypes.HANDLE
    _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX = _WINDOWS_KERNEL32.GetFileInformationByHandleEx
    _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX.restype = wintypes.BOOL
    _WINDOWS_SET_FILE_INFORMATION_BY_HANDLE = _WINDOWS_KERNEL32.SetFileInformationByHandle
    _WINDOWS_SET_FILE_INFORMATION_BY_HANDLE.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    _WINDOWS_SET_FILE_INFORMATION_BY_HANDLE.restype = wintypes.BOOL
    _WINDOWS_CLOSE_HANDLE = _WINDOWS_KERNEL32.CloseHandle
    _WINDOWS_CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
    _WINDOWS_CLOSE_HANDLE.restype = wintypes.BOOL


def _file_identity(metadata: os.stat_result) -> tuple[int, int]:
    """Return the volume and file identity captured for a staged file."""
    return int(metadata.st_dev), int(metadata.st_ino)


if sys.platform == "win32":

    def _windows_file_rename_info_ex_supported_by_os() -> bool:
        """Report whether Windows 10 build 14393 (RS1) or newer is running."""
        version = sys.getwindowsversion()
        return (version.major, version.minor, version.build) >= (
            10,
            0,
            _WINDOWS_FILE_RENAME_INFO_EX_MINIMUM_BUILD,
        )

    def _windows_rename_staged_handle(handle: int, target_path: Path) -> None:
        """Rename one open staged file handle with Windows POSIX replacement semantics."""
        target_name = os.fsdecode(os.fspath(target_path.absolute())).encode("utf-16-le")
        name_offset = _WindowsFileRenameInfoEx.file_name.offset
        information_size = max(
            ctypes.sizeof(_WindowsFileRenameInfoEx),
            name_offset + len(target_name) + ctypes.sizeof(wintypes.WCHAR),
        )
        information = ctypes.create_string_buffer(information_size)
        structure = ctypes.cast(information, ctypes.POINTER(_WindowsFileRenameInfoEx)).contents
        structure.flags = _WINDOWS_FILE_RENAME_REPLACE_IF_EXISTS | _WINDOWS_FILE_RENAME_POSIX_SEMANTICS
        structure.root_directory = None
        structure.file_name_length = len(target_name)
        ctypes.memmove(ctypes.addressof(information) + name_offset, target_name, len(target_name))

        if not _WINDOWS_SET_FILE_INFORMATION_BY_HANDLE(
            handle,
            _WINDOWS_FILE_RENAME_INFO_EX,
            ctypes.byref(information),
            len(information),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def _windows_replace_staged_file(staging_path: Path, target_path: Path, identity: tuple[int, int]) -> None:
        """Publish the exact reserved stage by handle, falling back only if unsupported."""
        access = _WINDOWS_DELETE | _WINDOWS_FILE_READ_ATTRIBUTES
        handle = _WINDOWS_CREATE_FILE(
            str(staging_path),
            access,
            _WINDOWS_FILE_SHARE_ALL,
            None,
            _WINDOWS_OPEN_EXISTING,
            _WINDOWS_FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        handle_value = getattr(handle, "value", handle)
        if handle_value is None or handle_value == _WINDOWS_INVALID_HANDLE:
            raise ctypes.WinError(ctypes.get_last_error())

        descriptor: int | None = None
        handle_owned_by_descriptor = False
        try:
            attributes = _WindowsFileAttributeTagInfo()
            if not _WINDOWS_GET_FILE_INFORMATION_BY_HANDLE_EX(
                handle_value,
                _WINDOWS_FILE_ATTRIBUTE_TAG_INFO,
                ctypes.byref(attributes),
                ctypes.sizeof(attributes),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes.file_attributes & _WINDOWS_FILE_ATTRIBUTE_REPARSE_POINT:
                raise OSError("hardened staging file must not be link-like")
            if attributes.file_attributes & _WINDOWS_FILE_ATTRIBUTE_DIRECTORY:
                raise OSError("hardened staging file must be a regular file")

            descriptor = msvcrt.open_osfhandle(handle_value, os.O_RDONLY | os.O_BINARY)
            handle_owned_by_descriptor = True
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or _file_identity(metadata) != identity:
                raise InternalInvariantError("hardened staging file identity changed before publication")

            if not _windows_file_rename_info_ex_supported_by_os():
                _replace_staged_path_after_identity_check(staging_path, target_path, identity)
                return

            try:
                _windows_rename_staged_handle(msvcrt.get_osfhandle(descriptor), target_path)
                return
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {
                    _WINDOWS_ERROR_INVALID_FUNCTION,
                    _WINDOWS_ERROR_NOT_SUPPORTED,
                }:
                    raise

            # The class or POSIX replacement flag is not supported by this
            # filesystem. Check that the reserved name still denotes the exact
            # file we opened before using the repository's canonical path replace.
            _replace_staged_path_after_identity_check(staging_path, target_path, identity)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            elif not handle_owned_by_descriptor:
                _WINDOWS_CLOSE_HANDLE(handle_value)


def _replace_staged_path_after_identity_check(
    staging_path: Path,
    target_path: Path,
    identity: tuple[int, int],
) -> None:
    """Use canonical replacement only while the reserved path still names our stage."""
    try:
        path_identity = _file_identity(os.stat(staging_path, follow_symlinks=False))
    except OSError as exc:
        raise InternalInvariantError("hardened staging path changed before fallback publication") from exc
    if path_identity != identity:
        raise InternalInvariantError("hardened staging path identity changed before fallback publication")
    os.replace(staging_path, target_path)


def _hardened_staging_path(path: Path) -> Path:
    """Return the collision-hardened staging sibling name for ``path``.

    The ``{pid}`` segment separates concurrent processes and the
    :func:`secrets.token_hex` segment makes the name unguessable, so a staging
    file next to an operator-chosen destination cannot be predicted, pre-created
    or waited on by anything that merely knows where the export is going.
    """
    return path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")


def _hardened_staging_flags() -> int:
    """Return the ``os.open`` flags shared by every hardened staging open."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= int(getattr(os, "O_NOINHERIT", 0))
    flags |= int(getattr(os, "O_CLOEXEC", 0))
    # O_BINARY is required on Windows: an fd opened without it is in text mode,
    # so os.write() translates every 0x0A byte to CRLF and silently corrupts
    # binary payloads (ciphertext, keys, PDFs) that contain a newline byte. The
    # flag is absent on POSIX, where getattr resolves to 0 (a no-op).
    flags |= int(getattr(os, "O_BINARY", 0))
    return flags


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


def atomic_write_best_effort_bytes(path: Path, data: bytes) -> None:
    """Atomically write ``data`` to ``path`` (best-effort tier, no fsync).

    Stages a :func:`tempfile.NamedTemporaryFile` sibling in ``path``'s parent
    directory (created if absent), writes it, then replaces ``path`` with
    :func:`os.replace`. Unlike the standard and hardened tiers, this tier never
    calls ``fsync`` on the tempfile or the parent directory: it exists for
    rebuildable derived caches where a torn write on crash only costs a
    recompute, not data loss, so the fsync cost is not worth paying on the
    write. The tempfile is unlinked on any failure, including a
    :class:`BaseException` raised mid-write. This tier never logs; the caller
    owns its own catch/log/swallow policy (see the module docstring).

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
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def atomic_write_best_effort_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically write ``text`` to ``path`` (best-effort tier, text variant).

    Encodes ``text`` and delegates to :func:`atomic_write_best_effort_bytes`;
    see its docstring for the write sequence and failure semantics.

    Args:
        path: Destination file. Parent directory is created if absent.
        text: Full file contents to write.
        encoding: Text encoding used to produce the bytes payload.
    """
    atomic_write_best_effort_bytes(path, text.encode(encoding))


class DurableWriteBatch:
    """Defer the per-file durability sync across many writes, flushing once.

    A hardened write costs three syncs — the staged fd, then the parent
    directory after :func:`os.replace`. Measured on this project's target
    platform that is ~3.5 ms/file against ~0.6 ms for the same write without
    them, so a bulk ingest of 20,000 evidence records spends about a minute
    on durability alone. This batch collapses that to one directory sync per
    touched directory at commit.

    **Only for content-addressed or re-derivable payloads.** The trade is
    real: a crash mid-batch can leave a file whose name is present but whose
    bytes never reached the platter. That is recoverable exactly when the
    reader can detect it and the caller can reproduce it — a blob named by the
    SHA-256 of its own contents fails its digest check on read and its source
    document is still on disk to re-import. It is NOT acceptable for key
    material, pointers, or session records: a torn key is neither detectable
    nor re-derivable, and those writers must keep the unbatched path.

    Explicit by construction. The batch is passed as an argument rather than
    bound to ambient context, because a durability policy that travels
    invisibly would silently weaken whichever unrelated write happened to run
    inside the scope.
    """

    __slots__ = ("_representatives",)

    def __init__(self) -> None:
        """Start an empty batch with no directories pending a sync."""
        # One written path per touched directory. Keyed by parent so a
        # thousand blobs in one namespace cost one sync, and the value is a
        # real written file so the shared :func:`fsync_parent_dir` helper is
        # called with the target it documents rather than a synthetic child.
        self._representatives: dict[Path, Path] = {}

    def note(self, path: Path) -> None:
        """Register ``path`` as the representative for its parent directory."""
        self._representatives.setdefault(path.parent, path)

    def commit(self) -> None:
        """Sync every directory touched by the batch, then forget them.

        Idempotent: the set is drained as it is synced, so an explicit
        ``commit()`` followed by the context manager's own commit on exit
        does not sync twice.
        """
        while self._representatives:
            _, representative = self._representatives.popitem()
            fsync_parent_dir(representative)


@contextmanager
def _hardened_staged_bytes(
    path: Path,
    data: bytes,
    *,
    mode: int,
    sync_file: bool,
) -> Generator[StagedPublication]:
    """Stage ``data`` through its exclusive descriptor and clean it if unpublished."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = _hardened_staging_path(path)
    descriptor = os.open(staging_path, _hardened_staging_flags(), mode)
    try:
        try:
            staged = StagedPublication(
                staging_path=staging_path,
                target_path=path,
                staging_identity=_file_identity(os.fstat(descriptor)),
            )
            write_all(descriptor, data)
            if sync_file:
                os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        staging_path.unlink(missing_ok=True)
        raise
    try:
        yield staged
    finally:
        if not staged.published:
            staging_path.unlink(missing_ok=True)


def atomic_write_hardened_bytes(
    path: Path,
    data: bytes,
    *,
    mode: int = _HARDENED_DEFAULT_MODE,
    batch: DurableWriteBatch | None = None,
) -> None:
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
        batch: Optional :class:`DurableWriteBatch`. When supplied, the write
            stays atomic but its two fsyncs are deferred to the batch commit.
            Pass one ONLY for content-addressed or otherwise re-derivable
            payloads; see :class:`DurableWriteBatch` for why key material,
            pointers and session records must not use it.

    Raises:
        OSError: When staging, writing, or replacing the file fails
            (including ``FileExistsError`` from an ``O_EXCL`` collision).
            The original exception propagates unwrapped; the tempfile is
            cleaned up first.
    """
    try:
        with _hardened_staged_bytes(path, data, mode=mode, sync_file=batch is None) as staged:
            if batch is None:
                staged.publish()
            else:
                # Batched: still atomic (O_EXCL staging + os.replace), but the two
                # syncs are deferred to the one commit. Atomicity and durability
                # are separate properties — a reader never sees a half-written
                # file either way; what the batch trades is only how soon the
                # bytes are guaranteed to survive a power loss.
                staged.publish_in_batch(batch)
        # Deliberately NO per-file ACL call here. ``mode`` covers POSIX; on
        # Windows the target's ACL comes from its parent directory, hardened
        # ONCE at creation with inheritance flags (see
        # ``core.file_permissions.restrict_directory_permissions``). A per-file
        # ``icacls`` strip was measured at ~28 ms/write, which is O(N)
        # subprocess spawns across the blob and journal writers — minutes of
        # pure overhead at the record counts this store is built for. Directory
        # inheritance gives the same confidentiality at O(1).
    except BaseException as exc:
        _log.error(
            "atomic_write: hardened-tier write failed target=%s error_type=%s",
            path,
            type(exc).__name__,
        )
        raise


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


class StagedPublication:
    """A reserved hardened staging file awaiting an explicit publication.

    Yielded by :func:`hardened_staged_publication` or
    :func:`hardened_staged_bytes_publication`. The caller writes the payload at
    :attr:`path` when using the path-oriented helper, then calls :meth:`publish`
    to move those bytes atomically onto the target. The bytes-oriented helper
    has already written and synced its payload through the exclusive
    descriptor. Leaving the context without publishing discards the staged file,
    so an interrupt, a
    refusal raised between the write and the publication, or an early return
    can never leave the payload stranded next to the target under a name the
    caller never told anyone about.

    Publication is a method rather than an automatic action on clean exit
    because the callers that need this tier write sensitive artefacts and must
    translate a publication ``OSError`` into their own typed refusal. A context
    manager that published on exit would raise from the ``with`` statement
    itself, where the caller can no longer distinguish a publication failure
    from a failure in its own body.
    """

    __slots__ = ("_published", "_staging_identity", "_staging_path", "_target_path")

    def __init__(
        self,
        *,
        staging_path: Path,
        target_path: Path,
        staging_identity: tuple[int, int],
    ) -> None:
        """Bind a reserved ``staging_path`` to the ``target_path`` it publishes onto."""
        self._staging_path = staging_path
        self._target_path = target_path
        self._staging_identity = staging_identity
        self._published = False

    @property
    def path(self) -> Path:
        """The reserved staging file the caller writes its payload to."""
        return self._staging_path

    @property
    def target_path(self) -> Path:
        """The destination :meth:`publish` moves the staged bytes onto."""
        return self._target_path

    @property
    def published(self) -> bool:
        """Whether :meth:`publish` has already moved the staged bytes into place."""
        return self._published

    def publish(self, *, replace_existing: bool = True) -> None:
        """Atomically move the staged bytes onto the target and sync its directory.

        With ``replace_existing`` false the publication is no-clobber: the
        staged inode is hard-linked to the target, which fails atomically when
        anything already occupies it, so a file that appeared after the
        caller's own existence check is refused rather than overwritten.

        Raises:
            FileExistsError: When ``replace_existing`` is false and the target
                exists at publication time.
            OSError: When the replace, the link or the directory sync fails. The
                staged file is left in place for the enclosing context manager to
                discard, so a failed publication never strands the payload.
            RuntimeError: When called a second time. One staging file publishes
                once; a second call would replace the target with a path the
                first call already consumed.
        """
        if replace_existing:
            self._publish_replace(batch=None)
        else:
            if self._published:
                raise InternalInvariantError("staged publication has already been published")
            os.link(self._staging_path, self._target_path)
            self._staging_path.unlink()
            fsync_parent_dir(self._target_path)
            self._published = True

    def publish_with_open_readers(self) -> None:
        """Atomically replace the target while delete-sharing readers retain snapshots.

        Windows refuses replacement while any open reader did not request
        delete sharing. On Windows this method uses the staged file's handle
        and POSIX rename semantics, which leave already-open delete-sharing
        handles attached to their old file while new opens resolve to the new
        target. Filesystems that explicitly report this rename capability as
        unsupported use the canonical ``os.replace`` fallback. Other errors
        propagate unchanged. On POSIX, this is the ordinary staged replace.

        The native rename binds publication to the verified reserved file
        handle. If an older Windows build or filesystem requires canonical
        path replacement, the current staging path identity is checked first
        and the existing path-based replacement semantics are retained.
        """
        if self._published:
            raise InternalInvariantError("staged publication has already been published")
        if sys.platform == "win32":
            _windows_replace_staged_file(self._staging_path, self._target_path, self._staging_identity)
        else:
            os.replace(self._staging_path, self._target_path)
        self._published = True
        fsync_parent_dir(self._target_path)

    def publish_in_batch(self, batch: DurableWriteBatch) -> None:
        """Replace the destination and defer its parent sync to ``batch``."""
        self._publish_replace(batch=batch)

    def _publish_replace(self, *, batch: DurableWriteBatch | None) -> None:
        if self._published:
            raise InternalInvariantError("staged publication has already been published")
        if batch is None:
            _replace_and_fsync(self._staging_path, self._target_path)
        else:
            os.replace(self._staging_path, self._target_path)
            batch.note(self._target_path)
        self._published = True


@contextmanager
def hardened_staged_bytes_publication(
    target_path: Path,
    data: bytes,
    *,
    mode: int = _HARDENED_DEFAULT_MODE,
) -> Generator[StagedPublication]:
    """Write hardened ``data`` once, then let the caller choose when to publish it.

    The staged bytes are written with :func:`write_all` through the original
    collision-hardened ``O_EXCL`` descriptor and fsynced before the context is
    entered. The yielded :class:`StagedPublication` can retry publication
    without reopening or rewriting the stage. If the context exits without a
    successful publication, the staged bytes are removed, including on a
    :class:`BaseException`.

    Use this when a complete byte payload is available but the caller must own
    the publication boundary, for example to apply a bounded platform-specific
    retry policy. Use :func:`hardened_staged_publication` when the caller must
    produce or inspect the file itself.

    Args:
        target_path: Destination the staged bytes are published onto. Its
            parent directory is created if absent; the target itself is not
            touched until :meth:`StagedPublication.publish` runs.
        data: Full file contents to stage through the exclusive descriptor.
        mode: POSIX file mode for the staged file (and, transitively, the
            published target). Defaults to ``0o600``.

    Yields:
        A :class:`StagedPublication` containing the fully written and synced
        bytes.

    Raises:
        OSError: When parent creation, staging, writing, syncing, or publication
            fails. The original exception propagates unwrapped; an unpublished
            stage is removed before it reaches the caller.
    """
    try:
        with _hardened_staged_bytes(target_path, data, mode=mode, sync_file=True) as staged:
            yield staged
    except BaseException as exc:
        _log.error(
            "atomic_write: deferred-bytes publication failed target=%s error_type=%s",
            target_path,
            type(exc).__name__,
        )
        raise


@contextmanager
def hardened_staged_publication(
    target_path: Path,
    *,
    mode: int = _HARDENED_DEFAULT_MODE,
) -> Generator[StagedPublication]:
    """Reserve a hardened staging sibling of ``target_path`` for a caller-driven write.

    The deferred-publish tier. Reserves an unguessable
    ``{name}.{pid}.{token_hex}.tmp`` sibling with the hardened tier's
    ``O_EXCL`` open at file mode ``mode``, yields it, and discards it on any
    exit that did not publish -- including a :class:`BaseException` such as the
    operator interrupting the work, which is precisely the case a narrow
    ``except OSError`` around a hand-rolled staging file misses.

    Use this tier when the payload cannot be handed over as ``bytes``: the
    producer builds the file incrementally, reads it back to verify it before
    it becomes operator-visible, or must complete unrelated work between the
    write and the publication. When the payload *is* in hand, use
    :func:`atomic_write_hardened_bytes` instead -- it is the same guarantees in
    one call.

    The reservation matters as much as the name. Opening with ``O_EXCL``
    refuses to adopt anything already sitting at the staging path, so the name
    handed to the caller is one this call claimed rather than one it inherited.
    A caller that writes in place keeps that inode; a caller that stages
    through its own replace supersedes it, and in both cases the name was
    never available to anyone else in between.

    Args:
        target_path: Destination the staged bytes are published onto. Its
            parent directory is created if absent; the target itself is not
            touched until :meth:`StagedPublication.publish` runs.
        mode: POSIX file mode for the reserved staging file (and, transitively,
            the published target). Defaults to ``0o600``.

    Yields:
        A :class:`StagedPublication` bound to the reserved staging file.

    Raises:
        OSError: When the parent directory or the staging reservation cannot be
            created (including ``FileExistsError`` from an ``O_EXCL``
            collision).
    """
    target_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path = _hardened_staging_path(target_path)
    descriptor = os.open(staging_path, _hardened_staging_flags(), mode)
    try:
        try:
            staging_identity = _file_identity(os.fstat(descriptor))
        finally:
            os.close(descriptor)
    except BaseException:
        staging_path.unlink(missing_ok=True)
        raise
    staged = StagedPublication(
        staging_path=staging_path,
        target_path=target_path,
        staging_identity=staging_identity,
    )
    try:
        yield staged
    except BaseException as exc:
        _log.error(
            "atomic_write: deferred-publish staging discarded target=%s error_type=%s",
            target_path,
            type(exc).__name__,
        )
        raise
    finally:
        if not staged.published:
            staging_path.unlink(missing_ok=True)


def _replace_and_fsync(tmp_path: Path, target: Path) -> None:
    """Replace ``target`` with ``tmp_path`` and best-effort fsync its parent."""
    os.replace(tmp_path, target)
    fsync_parent_dir(target)
