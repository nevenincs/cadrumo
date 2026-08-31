"""Shared collection-time process-private storage-root derivation.

Both the repo-root ``conftest.py`` and ``src/cadrumo/conftest.py`` must point
``CADRUMO_LOCAL_STORAGE_ROOT`` at a process-private temp directory BEFORE any
Cadrumo import resolves ``Settings`` — otherwise collection-time imports (CLI
and i18n modules transitively pulled in while pytest gathers tests) would
resolve the real platform state root, which may hold retired former-product
state and trip the cold-start guard. Both conftests derived the same
``<gettempdir()>/cadrumo-pytest-<pid>`` path independently; this module is the
single source for that derivation, plus a best-effort cleanup so the
per-invocation directories stop accumulating in the OS temp directory forever.

Pure-stdlib on purpose: importing this module must never resolve Settings,
configure logging, or trigger any other Cadrumo package side effect, so it is
safe to import from either conftest at the earliest point in collection.
"""

from __future__ import annotations

import atexit
import contextlib
import getpass
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from tempfile import gettempdir

from ..core.directory_scan import scan_directory

_STEM = "cadrumo-pytest-"

SETTINGS_STEM = "cadrumo-settings-"
"""Prefix for the temporary storage roots ``env_scope`` mints per call.

Declared here rather than at the mint site so the sweep below and the code
that creates them cannot disagree about the name -- ``env_scope`` imports this
constant instead of spelling it again. Importing this module is safe from
anywhere: it is pure stdlib and resolves no Settings.
"""

_SWEPT_STEMS = (_STEM, SETTINGS_STEM)
"""Every prefix the staleness sweep reclaims.

Both families leak by the same mechanism -- a process that is killed rather
than torn down runs neither its ``atexit`` hooks nor pytest's teardown -- and
on a shared box under load that is routine rather than exceptional. The
per-call roots additionally carry a session-scoped finalizer
(``env_scope.release_settings_storage_directories``), which is what handles the
normal path; this sweep is the complement that catches what a finalizer
structurally cannot.
"""

_STALE_AFTER_SECONDS = 24 * 60 * 60
"""Generous staleness threshold for a sibling root: long enough to never
race a slow CI run or a long-idle interactive session sharing the same
temp directory, short enough that crashed/killed prior invocations do not
accumulate indefinitely.

This is the ceiling that applies to every swept family, and it is
deliberately unchanged: mtime is only a PROXY for liveness -- a live
session that has simply not written for a while is indistinguishable from
an abandoned one -- so where mtime is the only available signal the
threshold has to out-wait the slowest plausible quiet period. The
``cadrumo-pytest-<pid>`` family carries a second, direct signal on top of
it (see :data:`_ABANDONED_AFTER_SECONDS`); the ``cadrumo-settings-``
family, whose names carry no owner, has only this one.
"""

_ABANDONED_AFTER_SECONDS = 10 * 60
"""Grace period applied only AFTER the owning process is confirmed gone.

A ``cadrumo-pytest-<pid>`` directory names its owner in its own filename,
so for that family liveness is directly observable rather than inferred
from mtime. Once the owning PID no longer resolves to a running process,
no live session can be using the directory -- that path is derived from
``os.getpid()`` and nothing else ever opens it -- so the slow-CI-run case
:data:`_STALE_AFTER_SECONDS` guards against cannot apply: a slow run's
process is alive by definition and is spared however long it idles.

The grace is therefore not a staleness estimate but a margin for the
things a liveness answer cannot cover: clock skew on the mtime read, and
a process that has just exited whose own ``atexit`` cleanup is still
mid-``rmtree``. Ten minutes is far beyond either and still bounds the
accrual at a fraction of a day's worth.
"""

_STILL_ACTIVE = 259
"""Windows ``GetExitCodeProcess`` sentinel meaning the process is running."""

_ERROR_INVALID_PARAMETER = 87
"""Windows ``OpenProcess`` error meaning no process carries that identifier."""


def process_is_live(pid: int) -> bool:
    """Report whether ``pid`` currently resolves to a running process.

    The single home for the probe every abandoned-scratch reclaim in this
    repository asks: the per-process storage roots swept below, the pytest
    numbered directories reaped by :func:`reap_abandoned_numbered_dirs`, and
    the operator-invoked temp reaper in the development tooling tree. Public
    rather than private because those consumers are real and the reasoning
    below must not be re-derived per caller -- a second probe is a second
    chance to get the Windows failure-mode handling wrong in the direction
    that deletes a live session's store.

    Fail-safe in one direction on purpose: every uncertain answer -- an
    unparseable identifier, a permission refusal, an unavailable platform
    facility -- reports ``True``, so the caller spares the directory. The
    sweep can therefore only ever retain something it might have reclaimed,
    never reclaim something it should have retained.

    PID reuse is the known unsoundness, and it lands on the safe side too: a
    recycled identifier makes an abandoned directory look owned, which costs
    one more day of retention before :data:`_STALE_AFTER_SECONDS` reclaims it
    anyway. It cannot make a live directory look abandoned.

    Ordering matters and is satisfied structurally by querying per directory
    rather than against a pre-taken snapshot: the directory listing happens
    first, so any directory under consideration was created by a process that
    already existed when the listing was taken. A process that starts later
    has no entry in that listing, and so can never be judged dead.
    """
    if pid <= 0:
        return True
    if sys.platform == "win32":
        return _windows_process_is_live(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _windows_process_is_live(pid: int) -> bool:
    """Windows liveness probe, via ``ctypes`` so the module stays pure-stdlib.

    ``os.kill(pid, 0)`` is NOT usable here: on Windows CPython routes any
    signal other than the console-control events to ``TerminateProcess``, so
    the POSIX liveness idiom would kill the very process it asks about.
    """
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)

        query_limited_information = 0x1000
        handle = kernel32.OpenProcess(query_limited_information, False, pid)
        if not handle:
            return ctypes.get_last_error() != _ERROR_INVALID_PARAMETER
        try:
            exit_code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return True
            return exit_code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    except (ImportError, OSError, AttributeError, ValueError):
        return True


def _owning_pid(sibling: Path, stem: str) -> int | None:
    """Return the PID encoded in ``sibling``'s name, or ``None`` if it carries none."""
    if stem != _STEM:
        return None
    suffix = sibling.name[len(stem) :]
    if not suffix.isdigit():
        return None
    try:
        return int(suffix)
    except ValueError:
        return None


def _is_reclaimable(sibling: Path, stem: str, reference: float) -> bool:
    """Decide whether ``sibling`` may be removed, erring towards retention.

    Two independent grounds, either sufficient:

    * the mtime ceiling (:data:`_STALE_AFTER_SECONDS`), the only rule that
      applies to a family whose names carry no owner; and
    * the owning process is confirmed gone and the short abandonment grace
      (:data:`_ABANDONED_AFTER_SECONDS`) has elapsed.

    The second is strictly additive: it reclaims sooner where a direct
    liveness answer exists, and never widens what the first alone would take.
    """
    age = reference - sibling.stat().st_mtime
    if age > _STALE_AFTER_SECONDS:
        return True
    if age <= _ABANDONED_AFTER_SECONDS:
        return False
    pid = _owning_pid(sibling, stem)
    return pid is not None and not process_is_live(pid)


def sweep_stale_roots(parent: Path, *, now: float | None = None, exclude: Path | None = None) -> int:
    """Remove swept-prefix directories under ``parent`` that no live session owns.

    Split out of the ``atexit`` hook so the reclaim rule can be exercised
    directly: a sweep reachable only through interpreter shutdown is a sweep
    nothing can prove reclaims the right things, or spares the wrong ones --
    and, more sharply, a sweep that runs ONLY at a clean exit runs only in the
    case where it was not needed. A process that is killed leaves its
    directory behind and skips the sweep in the same stroke, so the reclaim
    has to happen at session START to reach anything.

    Safe to run concurrently from many processes: nothing it removes belongs
    to a live session, so a directory two sweepers reach at once can be
    partially removed without any run observing the difference, and
    ``ignore_errors=True`` absorbs the resulting races.

    Best-effort throughout -- a locked file or a permission error is swallowed.
    This is tidiness, not correctness: a stale root is self-invalidating on
    next use, because a fresh PID never reuses an old directory.

    Args:
        parent: Directory to sweep, normally the OS temp directory.
        now: Reference time, defaulting to the wall clock. Injectable so a test
            can age a directory without waiting a day for it.
        exclude: A directory to leave alone regardless of every other rule,
            normally the calling process's own root. Its PID is live, so the
            liveness rule already spares it; naming it explicitly means a
            caller never depends on that reasoning holding.

    Returns:
        How many directories were removed.
    """
    reference = time.time() if now is None else now
    spared = None if exclude is None else exclude.name
    removed = 0
    for stem in _SWEPT_STEMS:
        try:
            siblings = list(scan_directory(parent, pattern=f"{stem}*"))
        except OSError:
            continue
        for sibling in siblings:
            if sibling.name == spared:
                continue
            try:
                reclaimable = _is_reclaimable(sibling, stem, reference)
            except OSError:
                continue
            if reclaimable:
                shutil.rmtree(sibling, ignore_errors=True)
                removed += 1
    return removed


_NUMBERED_STEMS = ("pytest-", "garbage-")
"""Prefixes pytest's ``tmp_path`` factory leaves under its per-user root.

``pytest-<n>`` is one session's numbered directory; ``garbage-<uuid>`` is the
rename target pytest's own cleanup moves a directory to just before removing
it, which survives whenever that removal is interrupted. Both carry the same
``.lock`` file naming the same kind of owner, so both reclaim under one rule.
"""

_LOCK_NAME = ".lock"
"""pytest's per-numbered-directory lock file (``_pytest.pathlib.get_lock_path``).

Created once with ``O_EXCL`` at directory creation, holding the owning
session's PID as its entire contents, and unlinked by an ``atexit`` hook on a
clean exit. Its mtime is NOT a heartbeat -- nothing refreshes it for the life
of the session -- so the file answers "who owns this" directly and answers
"is that owner still running" not at all. That split is the whole design here:
the PID is read from the file and the liveness question is put to the OS.
"""


def pytest_numbered_dir_root(temproot: Path | None = None) -> Path:
    """Return pytest's per-user numbered-directory root.

    Derived the way ``_pytest.tmpdir.TempPathFactory.getbasetemp`` derives it
    -- ``<temproot>/pytest-of-<user>``, falling back to ``pytest-of-unknown``
    when the user cannot be resolved -- rather than spelled as a literal, so a
    box whose user differs from the one this leak was measured on is reaped
    too.
    """
    try:
        user: str | None = getpass.getuser()
    except (OSError, ImportError, KeyError):
        user = None
    root = temproot if temproot is not None else Path(gettempdir())
    return root / f"pytest-of-{user or 'unknown'}"


def _numbered_dir_owner_pid(directory: Path) -> int | None:
    """Return the PID recorded in ``directory``'s pytest lock file, if any.

    ``None`` covers every shape that is not a readable PID: no lock file at
    all, an unreadable one, and contents that do not parse. Each lands the
    caller on the mtime ceiling rather than on a liveness answer, which is the
    conservative direction -- a missing lock is genuinely ambiguous, because
    pytest creates the numbered directory and writes the lock in two separate
    steps and a directory observed between them has no lock yet.
    """
    lock = directory / _LOCK_NAME
    try:
        if not lock.is_file():
            return None
        contents = lock.read_text(encoding="utf-8", errors="strict").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not contents.isdigit():
        return None
    try:
        return int(contents)
    except ValueError:
        return None


def _numbered_dir_is_reclaimable(directory: Path, reference: float) -> bool:
    """Decide whether a pytest numbered directory may be removed.

    The same two-ground rule :func:`_is_reclaimable` applies to the per-process
    storage roots, reading the owner from the lock file's contents rather than
    from the directory's own name:

    * the mtime ceiling (:data:`_STALE_AFTER_SECONDS`), which is the only rule
      available when the lock is absent or unreadable; and
    * the owning process is confirmed gone and :data:`_ABANDONED_AFTER_SECONDS`
      has elapsed.

    The second ground is what pytest structurally cannot apply itself.
    ``_pytest.pathlib.ensure_deletable`` compares the lock's mtime against
    ``LOCK_TIMEOUT``, a module constant of three days with no ini override, and
    since nothing ever refreshes that mtime the comparison is against the
    directory's creation time. A session killed one minute in therefore holds
    its whole tree for three days. pytest has to reason that way: it never
    reads the PID back out of the lock, so age is the only thing it can ask.
    Reading the PID and asking the OS answers the question pytest is
    approximating, and answers it in minutes instead of days.
    """
    age = reference - directory.stat().st_mtime
    if age > _STALE_AFTER_SECONDS:
        return True
    if age <= _ABANDONED_AFTER_SECONDS:
        return False
    pid = _numbered_dir_owner_pid(directory)
    return pid is not None and not process_is_live(pid)


def reap_abandoned_numbered_dirs(root: Path, *, now: float | None = None) -> tuple[int, int]:
    """Remove pytest numbered directories under ``root`` that no live session owns.

    Complements pytest's own garbage collection rather than competing with it.
    pytest reclaims a numbered directory only once it falls outside the
    retained-session count AND its lock has aged past the three-day
    ``LOCK_TIMEOUT``; this reclaims the ones whose owner is provably gone,
    which is the population that three-day hold accumulates. On this box a
    numbered directory is minted roughly every twenty seconds, so a
    three-day hold over crashed sessions is the accrual mechanism, not an
    edge case.

    Symbolic links are skipped outright and never followed. ``pytest-current``
    is a link pytest maintains to the newest directory, and following it would
    turn a link removal into a removal of a live session's tree.

    Safe to run concurrently and repeatedly, for the same reason
    :func:`sweep_stale_roots` is: nothing it removes belongs to a live session,
    so two reapers reaching one directory at once cannot make any run observe a
    difference, and every filesystem error is swallowed.

    Args:
        root: pytest's per-user numbered-directory root, normally
            :func:`pytest_numbered_dir_root`.
        now: Reference time, defaulting to the wall clock. Injectable so a test
            can age a directory rather than wait out the grace.

    Returns:
        ``(removed, spared)`` -- how many directories were removed, and how
        many candidates were examined and left alone. The spared count is the
        reported safety evidence: a reaper that removed everything and a
        reaper that removed only what it should both report a removal count.
    """
    reference = time.time() if now is None else now
    removed = 0
    spared = 0
    for stem in _NUMBERED_STEMS:
        try:
            candidates = list(scan_directory(root, pattern=f"{stem}*"))
        except OSError:
            continue
        for candidate in candidates:
            try:
                if candidate.is_symlink() or not candidate.is_dir():
                    continue
                reclaimable = _numbered_dir_is_reclaimable(candidate, reference)
            except OSError:
                spared += 1
                continue
            if reclaimable:
                shutil.rmtree(candidate, ignore_errors=True)
                removed += 1
            else:
                spared += 1
    return removed, spared


def collection_storage_root() -> Path:
    """Return this process's private collection-time storage root.

    ``<gettempdir()>/cadrumo-pytest-<pid>`` — process-private by construction
    (keyed on the current PID), so concurrent pytest invocations, including
    parallel agents sharing this worktree, never collide.
    """
    return Path(gettempdir()) / f"{_STEM}{os.getpid()}"


def _release_log_handlers_under(root: Path) -> None:
    """Close and detach any root-logger file handler writing under ``root``.

    ``configure_logging`` (``cadrumo.core.logging``) attaches a
    ``RotatingFileHandler`` under this process's own storage root, and the
    stdlib ``logging`` module registers its own ``atexit.register(logging.shutdown)``
    at import time -- long before this module's cleanup is registered during
    conftest collection. ``atexit`` runs callbacks in reverse registration
    order, so this cleanup fires BEFORE ``logging.shutdown()`` closes that
    handler: the log file is still open when ``shutil.rmtree`` below runs.
    Windows refuses to delete an open file, and ``ignore_errors=True``
    swallows that failure silently, so the root's cleanup was never actually
    succeeding at process exit -- confirmed by measurement, reproducible on
    every run. It only ever cleared later, once a *different* process's stale
    sweep found the same root after the lock had already been released.

    Closing the handler here (rather than calling the blanket
    ``logging.shutdown()``) is deliberately narrow: it releases only the file
    this cleanup is about to delete, leaving any other handler (stderr,
    a per-run JSONL sink pointed elsewhere) untouched for whatever other
    ``atexit`` callback still expects to use it.
    """
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        base_filename = getattr(handler, "baseFilename", None)
        if base_filename is None:
            continue
        try:
            under_root = Path(base_filename).resolve().is_relative_to(root.resolve())
        except OSError:
            continue
        if not under_root:
            continue
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except OSError:
            continue


def register_collection_storage_root_cleanup(root: Path) -> None:
    """Sweep abandoned sibling roots NOW, and register cleanup of ``root`` at exit.

    Called once per pytest process by both conftests, at the earliest safe
    point in collection, which makes it the one moment guaranteed to execute
    regardless of how any previous process died. The sweep runs here, before
    the ``atexit`` registration, for exactly that reason: an exit-only sweep
    is unreachable in the case it exists for. A process that is killed rather
    than torn down runs neither its ``atexit`` hooks nor pytest's teardown, so
    it leaves its directory behind AND skips the sweep that would have
    reclaimed its predecessors'. Only clean exits ever swept, and a clean exit
    has already removed its own root -- the reclaim could only run when it was
    not needed.

    Measured on the shared development box before this ran at startup: 137
    ``cadrumo-pytest-*`` directories spanning a single day, each holding a
    SQLite database plus its write-ahead-log sidecar, accruing faster than the
    24h mtime ceiling released them, on the way to filling the system volume.

    pytest's own numbered directories are reaped from here too. They leak by
    the same mechanism and are reclaimed under the same rule, and this is the
    only hook on the box guaranteed to run often enough to bound them -- the
    reaper's whole cost is one directory listing of a dozen-odd entries plus a
    liveness probe per entry, which is why putting it on the critical path of
    every test session is affordable where a recursive walk would not be. It
    is deliberately NOT excluded against this process's own numbered directory:
    that directory may not exist yet at collection time, and when it does its
    lock names this live process, so the liveness rule already spares it.

    The exit hook is retained unchanged: it correctly handles the clean path,
    where removing this process's own root the moment it finishes is better
    than leaving it for a successor to find.

    Both the removal and the sweep are best-effort: a locked file or a
    permission error is swallowed rather than raised, since this is tidiness,
    not correctness — a stale root, like a stale registry cache pickle, is
    self-invalidating on next use because a fresh PID never reuses an old
    directory.
    """
    with contextlib.suppress(OSError):
        sweep_stale_roots(root.parent, exclude=root)
    with contextlib.suppress(OSError):
        reap_abandoned_numbered_dirs(pytest_numbered_dir_root(root.parent))

    def _cleanup() -> None:
        _release_log_handlers_under(root)
        shutil.rmtree(root, ignore_errors=True)
        sweep_stale_roots(root.parent, exclude=root)

    atexit.register(_cleanup)


def apply_collection_storage_root(*, overwrite: bool = False) -> Path:
    """Derive the collection-time root, apply it, and register cleanup in one call.

    A single bare expression-statement call is deliberate: both conftests must
    perform this setup AFTER their own top-of-file imports but BEFORE a further
    block of imports that must not resolve ``Settings`` early, and a bound
    module-level assignment ahead of those later imports triggers ruff's
    ``E402`` (module-level import not at top of file) — an expression
    statement with a discarded return value does not. Callers that need the
    resolved root value should call :func:`collection_storage_root` directly
    instead of relying on this function's return value.

    Args:
        overwrite: When ``True``, unconditionally overwrite
            ``CADRUMO_LOCAL_STORAGE_ROOT`` (``src/cadrumo/conftest.py``'s
            historical behaviour). When ``False`` (default), only set it if
            unset (the repo-root ``conftest.py``'s historical
            ``os.environ.setdefault`` behaviour, since the root conftest loads
            first and must not clobber a value the nested conftest already set
            for the same process).
    """
    root = collection_storage_root()
    if overwrite:
        os.environ["CADRUMO_LOCAL_STORAGE_ROOT"] = str(root)
    else:
        os.environ.setdefault("CADRUMO_LOCAL_STORAGE_ROOT", str(root))
    register_collection_storage_root_cleanup(root)
    return root
