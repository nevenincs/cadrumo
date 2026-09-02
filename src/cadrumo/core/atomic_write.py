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

- **Standard tier** (:func:`atomic_write_bytes`, :func:`atomic_write_stream`,
  :func:`atomic_write_text`): a :func:`tempfile.NamedTemporaryFile` sibling in
  the target's own parent directory (``{stem}.`` prefix, ``.tmp`` suffix),
  write, flush, ``fsync``, :func:`os.replace`, then a best-effort
  parent-directory ``fsync`` via :func:`~cadrumo.core.fsync.fsync_parent_dir`.
  The stream variant bounds memory to its caller's chunk size. Suitable for
  ordinary durable application data with a single writer.

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

- **Publish-once tier** (:func:`atomic_write_publish_once_bytes`): the hardened
  tier's staging exactly, but published with :func:`os.link` rather than
  :func:`os.replace`, so an existing target raises :exc:`FileExistsError` in one
  uninterruptible step instead of being overwritten. For write-once evidence --
  a provenance manifest, an attestation -- where a second write is a bug rather
  than an update. This exists because ``if path.exists(): raise`` before a
  replace is not the same guarantee: it leaves a window between the check and
  the publication, and callers open-coding that pattern were re-implementing
  the staging dialect around it.

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
import tempfile
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from pathlib import Path

from .fsync import fsync_parent_dir
from .logging import get_logger

__all__ = [
    "DurableWriteBatch",
    "StagedPublication",
    "atomic_write_best_effort_bytes",
    "atomic_write_best_effort_text",
    "atomic_write_bytes",
    "atomic_write_hardened_bytes",
    "atomic_write_hardened_text",
    "atomic_write_publish_once_bytes",
    "atomic_write_stream",
    "atomic_write_text",
    "durable_write_batch",
    "hardened_staged_publication",
]

_log = get_logger(__name__)

_HARDENED_DEFAULT_MODE = 0o600


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


def atomic_write_stream(path: Path, chunks: Iterable[bytes]) -> int:
    """Atomically stream ``chunks`` to ``path`` and return the byte count.

    The stream is staged in a sibling tempfile, flushed and fsynced before it
    replaces the target. An iterator failure therefore preserves the prior
    target and removes its partial staging file without requiring callers to
    buffer an unbounded payload in memory.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    length = 0
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent,
            prefix=f"{path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            tmp_path = Path(handle.name)
            for chunk in chunks:
                handle.write(chunk)
                length += len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_and_fsync(tmp_path, path)
        tmp_path = None
        return length
    except BaseException as exc:
        _log.error(
            "atomic_write: streamed write failed target=%s error_type=%s",
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
def durable_write_batch() -> Generator[DurableWriteBatch]:
    """Yield a :class:`DurableWriteBatch` and commit it on exit.

    Commits from a ``finally``, so an exception mid-batch still syncs whatever
    already landed rather than leaving the completed writes less durable than
    an unbatched run would have.
    """
    batch = DurableWriteBatch()
    try:
        yield batch
    finally:
        batch.commit()


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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _hardened_staging_path(path)
    flags = _hardened_staging_flags()
    created = False
    try:
        fd = os.open(tmp_path, flags, mode)
        created = True
        try:
            _write_all(fd, data)
            if batch is None:
                os.fsync(fd)
        finally:
            os.close(fd)
        if batch is None:
            _replace_and_fsync(tmp_path, path)
        else:
            # Batched: still atomic (O_EXCL staging + os.replace), but the two
            # syncs are deferred to the one commit. Atomicity and durability
            # are separate properties — a reader never sees a half-written
            # file either way; what the batch trades is only how soon the
            # bytes are guaranteed to survive a power loss.
            os.replace(tmp_path, path)
            batch.note(path)
        created = False
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


def atomic_write_publish_once_bytes(
    path: Path,
    data: bytes,
    *,
    mode: int = _HARDENED_DEFAULT_MODE,
) -> None:
    """Atomically write ``data`` to ``path``, refusing a pre-existing target.

    The publish-once tier. Stages exactly as the hardened tier does -- ``O_EXCL``
    plus ``O_NOINHERIT``/``O_CLOEXEC`` where defined, file mode ``mode``, a
    collision-hardened ``{name}.{pid}.{token_hex}.tmp`` sibling, a
    memoryview-and-offset write loop, and an ``fsync`` before publication -- then
    publishes with :func:`os.link` instead of :func:`os.replace`.

    That substitution is the entire point of the tier. :func:`os.replace`
    overwrites an existing target by definition; :func:`os.link` fails with
    :exc:`FileExistsError` in one uninterruptible step. A caller that must never
    overwrite therefore gets a real guarantee here, where open-coding
    ``if path.exists(): raise`` before a replace leaves a window between the
    check and the publication. Use this tier for write-once evidence: a
    provenance manifest, an attestation, any record whose second write is a bug
    rather than an update.

    The staging file is unlinked after a successful link and on any failure,
    including a :class:`BaseException` raised mid-write, so no orphan sibling
    survives either path. Both names refer to one inode between the link and
    that unlink, which is why the parent directory is fsynced only afterwards.

    Args:
        path: Destination file, which MUST NOT already exist. Parent directory
            is created if absent.
        data: Full file contents to write.
        mode: POSIX file mode for the staged tempfile (and, transitively, the
            published target). Defaults to ``0o600``.

    Raises:
        FileExistsError: When ``path`` already exists. This is the tier's
            contract, not an incidental failure.
        OSError: When staging, writing, or linking otherwise fails. The original
            exception propagates unwrapped; the tempfile is cleaned up first.
            Note that :func:`os.link` requires the staging sibling and the
            target to share a filesystem, which holds by construction because
            staging is always a sibling of ``path``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _hardened_staging_path(path)
    flags = _hardened_staging_flags()
    created = False
    refused_existing_target = False
    try:
        fd = os.open(tmp_path, flags, mode)
        created = True
        try:
            _write_all(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.link(tmp_path, path)
        except FileExistsError:
            # Narrowed to the link step on purpose. Refusing an existing target
            # is this tier's contract, not an incident, so it is not logged as
            # an error -- but `FileExistsError` is NOT unique to that step:
            # `mkdir` raises it when a parent path component is a regular file,
            # and the `O_EXCL` open raises it on a staging-name collision.
            # Both of those are genuine failures. Catching the bare type around
            # the whole body silently reclassified them as the contract.
            refused_existing_target = True
            raise
        fsync_parent_dir(path)
    except BaseException as exc:
        if refused_existing_target:
            raise
        _log.error(
            "atomic_write: publish-once write failed target=%s error_type=%s",
            path,
            type(exc).__name__,
        )
        raise
    finally:
        if created:
            tmp_path.unlink(missing_ok=True)


class StagedPublication:
    """A reserved hardened staging file awaiting an explicit publication.

    Yielded by :func:`hardened_staged_publication`. The caller writes the
    payload at :attr:`path` by whatever means its producer requires, then calls
    :meth:`publish` to move those bytes atomically onto the target. Leaving the
    context without publishing discards the staged file, so an interrupt, a
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

    __slots__ = ("_published", "_staging_path", "_target_path")

    def __init__(self, *, staging_path: Path, target_path: Path) -> None:
        """Bind a reserved ``staging_path`` to the ``target_path`` it publishes onto."""
        self._staging_path = staging_path
        self._target_path = target_path
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

    def publish(self) -> None:
        """Atomically move the staged bytes onto the target and sync its directory.

        Raises:
            OSError: When the replace or the directory sync fails. The staged
                file is left in place for the enclosing context manager to
                discard, so a failed publication never strands the payload.
            RuntimeError: When called a second time. One staging file publishes
                once; a second call would replace the target with a path the
                first call already consumed.
        """
        if self._published:
            raise RuntimeError("staged publication has already been published")
        _replace_and_fsync(self._staging_path, self._target_path)
        self._published = True


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
    os.close(os.open(staging_path, _hardened_staging_flags(), mode))
    staged = StagedPublication(staging_path=staging_path, target_path=target_path)
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
