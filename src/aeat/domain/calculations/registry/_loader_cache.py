"""Registry loader cache predicates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from ....core.resources import bundled_path

# The bundled tree gets a longer fingerprint TTL than a mutable authoring
# tree, but NOT a process-lifetime one: under an editable install (the
# routine dev/worktree mode) "bundled" resolves to the literal in-tree
# ``src/aeat/_data/registry/aeat`` source directory, which concurrent peer
# agents in this shared worktree edit live throughout a session. A TTL that
# never re-checks would silently serve stale registry TOML to a long-running
# process (an MCP server, a REPL, a background watch loop) after such an
# edit lands. 10 seconds is long enough to fold the several fingerprint
# recomputations one calculate call triggers (authority + snapshot + any
# nested revision lookups, all milliseconds apart) into a single directory
# walk, while still re-scanning promptly enough that a concurrent registry
# edit is picked up well within one operator interaction. A genuinely
# read-only installed (non-editable) wheel benefits identically: nothing
# ever rewrites it, so the periodic re-walk merely repeats the same answer.
BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS = 10.0
MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS = 1.0


@lru_cache(maxsize=1)
def _bundled_registry_root() -> Path:
    """Return the resolved package-bundled registry root, computed once per process."""
    return bundled_path("registry", "aeat").resolve()


def is_bundled_registry_root(resolved: Path) -> bool:
    """Whether ``resolved`` is the package-bundled registry tree.

    The bundled tree is shipped inside the installed wheel (or, under an
    editable install, force-included from the in-tree ``registry/aeat``
    directory) rather than passed explicitly as a mutable authoring tree
    (e.g. a test's ``tmp_path`` fixture building a synthetic registry).
    Comparing the resolved path against the bundled root lets the
    fingerprint cache apply :data:`BUNDLED_REGISTRY_FINGERPRINT_TTL_SECONDS`
    to the bundled tree alone without weakening invalidation for any
    mutable tree, which always keeps the strict
    :data:`MUTABLE_REGISTRY_FINGERPRINT_TTL_SECONDS` window.
    """
    try:
        return resolved == _bundled_registry_root()
    except (ImportError, OSError, ValueError):
        # A resources boundary failure (e.g. no bundled data under an unusual
        # install) must never be mistaken for "this is the bundled tree";
        # fail closed to the strict mutable-tree TTL.
        return False


def registry_disk_cache_enabled() -> bool:
    """Whether the cross-process ``/tmp`` registry pickle is read/written.

    Disabled under pytest, including collection before ``PYTEST_CURRENT_TEST``
    is set: the pickle is keyed by file mtime and shared across pytest-xdist
    workers, so a parallel run could serve a stale compiled registry from one
    worker to another. Production loads the registry once at startup with no
    concurrent edits, so it keeps the disk cache.
    """
    import os
    import sys

    if "pytest" in sys.modules:
        return False
    return (
        "PYTEST_CURRENT_TEST" not in os.environ
        and "PYTEST_XDIST_WORKER" not in os.environ
        and "PYTEST_VERSION" not in os.environ
    )
