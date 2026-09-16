"""The one canonical resolver for `dev/` tooling's derived-cache location.

Every persistent cache the development tooling keeps is derived output of one
checkout: registry pickles, validation verdicts, extracted record designs,
corpus text, runtime wheels, packaging proofs. Seven modules each resolved their own
path below one hidden directory in the user's home, so the output of every
worktree on the machine accumulated in a tree no checkout owned.
Nothing rebuilt it, nothing swept it, deleting a worktree did not shrink it,
and it reached tens of thousands of files before anyone looked inside.

Resolution order, for every cache alike:

1. The cache's OWN environment override, where it has one
   (``CADRUMO_REGISTRY_DISK_CACHE_DIR`` and friends). Each cache reads its own,
   because a test pinning an exclusive store needs to move one cache without
   moving the rest. That check lives at the cache, not here.
2. :data:`DEV_CACHE_ROOT_ENV`, the shared root override, which relocates every
   cache at once. A runner placing derived output on another volume, or a
   developer keeping it off the checkout's filesystem, sets this one variable.
3. ``<repository root>/.cache``, the default, which ``.gitignore`` excludes.

The fallback is the checkout's own directory and nothing else. The user's home
directory is where an EXTERNAL tool keeps its state; it is never where this
project keeps output whose only reader is one worktree. A cache that outlives
its inputs' only reader is not a cache, it is litter.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from ._paths import REPO_ROOT

DEV_CACHE_ROOT_ENV: Final[str] = "CADRUMO_DEV_CACHE_ROOT"
"""Environment variable relocating every development cache at once."""

DEFAULT_DEV_CACHE_ROOT: Final[Path] = REPO_ROOT / ".cache"
"""Where the caches land when :data:`DEV_CACHE_ROOT_ENV` is unset or blank."""


def dev_cache_root() -> Path:
    """Resolve the directory holding this checkout's development caches.

    A blank value is treated as unset, matching ``Settings``'
    ``env_ignore_empty`` behaviour, so a variable exported empty by a shell
    profile or a CI matrix does not resolve the caches to the process's current
    working directory.

    Returns:
        The configured root, or ``<repository root>/.cache`` when none is set.
    """
    override = os.environ.get(DEV_CACHE_ROOT_ENV, "").strip()
    if override:
        return Path(override)
    return DEFAULT_DEV_CACHE_ROOT


def dev_cache_dir(name: str) -> Path:
    """Return the default directory for the development cache called ``name``.

    The directory is not created; each cache creates its own on first write, so
    resolving a location stays free of side effects.

    Args:
        name: The cache's family name, used verbatim as the directory name.

    Returns:
        ``<development cache root>/<name>``.

    Raises:
        ValueError: When ``name`` is blank or is not a single path segment.
    """
    if not name.strip() or name != name.strip():
        raise ValueError(f"cache name must be a non-blank, unpadded segment, got {name!r}")
    if len(Path(name).parts) != 1 or name in {".", ".."}:
        raise ValueError(f"cache name must be a single path segment, got {name!r}")
    return dev_cache_root() / name


__all__ = ["DEFAULT_DEV_CACHE_ROOT", "DEV_CACHE_ROOT_ENV", "dev_cache_dir", "dev_cache_root"]
