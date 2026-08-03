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
import os
import shutil
import time
from pathlib import Path
from tempfile import gettempdir

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
accumulate indefinitely."""


def sweep_stale_roots(parent: Path, *, now: float | None = None) -> int:
    """Remove swept-prefix directories under ``parent`` older than the threshold.

    Split out of the ``atexit`` hook so the staleness rule can be exercised
    directly: a sweep reachable only through interpreter shutdown is a sweep
    nothing can prove reclaims the right things, or spares the wrong ones.

    Best-effort throughout -- a locked file or a permission error is swallowed.
    This is tidiness, not correctness: a stale root is self-invalidating on
    next use, because a fresh PID never reuses an old directory.

    Args:
        parent: Directory to sweep, normally the OS temp directory.
        now: Reference time, defaulting to the wall clock. Injectable so a test
            can age a directory without waiting a day for it.

    Returns:
        How many directories were removed.
    """
    reference = time.time() if now is None else now
    removed = 0
    for stem in _SWEPT_STEMS:
        try:
            siblings = list(parent.glob(f"{stem}*"))
        except OSError:
            continue
        for sibling in siblings:
            try:
                if reference - sibling.stat().st_mtime > _STALE_AFTER_SECONDS:
                    shutil.rmtree(sibling, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
    return removed


def collection_storage_root() -> Path:
    """Return this process's private collection-time storage root.

    ``<gettempdir()>/cadrumo-pytest-<pid>`` — process-private by construction
    (keyed on the current PID), so concurrent pytest invocations, including
    parallel agents sharing this worktree, never collide.
    """
    return Path(gettempdir()) / f"{_STEM}{os.getpid()}"


def register_collection_storage_root_cleanup(root: Path) -> None:
    """Register best-effort cleanup for ``root`` and any stale sibling directories.

    Removes ``root`` at process exit (``atexit``) and sweeps every stale
    sibling carrying a swept prefix (see :data:`_SWEPT_STEMS`), so
    per-invocation directories from past runs — crashed sessions, killed
    workers — do not accumulate indefinitely in the OS temp directory. Both the
    removal and the sweep are best-effort: a locked file or a permission error
    is swallowed rather than raised, since this is tidiness, not correctness —
    a stale root, like a stale registry cache pickle, is self-invalidating on
    next use because a fresh PID never reuses an old directory.
    """

    def _cleanup() -> None:
        shutil.rmtree(root, ignore_errors=True)
        sweep_stale_roots(root.parent)

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
