"""Registry loader cache predicates.

This module centralizes the small policy decisions that keep registry loading
fast without hiding live TOML edits. Bundled registry roots receive a short
fingerprint TTL, mutable authoring roots keep the stricter window, and under
pytest the cross-process disk pickle is shared only for the immutable
bundled root -- a mutable/synthetic root always keeps it disabled so xdist
workers cannot share a stale compiled registry from a tree the run itself
can edit.

See Also:
    :mod:`~domain.calculations.registry._loader`
        Registry TOML loader that consumes these TTL and disk-cache predicates.
    :func:`~core.resources.bundled_path`
        Resource boundary used to identify the package-bundled registry root.
    :func:`~domain.calculations.registry.tests.test_loader_cache_isolation.test_registry_disk_cache_disabled_under_pytest`
        Real-behavior gate for the pytest disk-cache refusal path.
    :func:`~domain.calculations.registry.tests.test_loader_cache_isolation.test_is_bundled_registry_root_rejects_a_mutable_authoring_tree`
        Coverage for bundled-root versus mutable-authoring-tree separation.
    :func:`~domain.calculations.registry.tests.test_loader_cache_isolation.test_bundled_tree_fingerprint_cache_survives_past_the_mutable_tree_ttl`
        Coverage for the longer bundled-root fingerprint TTL window.
    :func:`~conftest._isolate_registry_caches`
        Session fixture that clears registry caches around pytest runs.
"""

from __future__ import annotations

import hashlib
import tempfile
from functools import lru_cache
from pathlib import Path

from ....core.config import load_settings
from ....core.resources import bundled_path
from ._errors import RegistryLoadError

REGISTRY_DISK_CACHE_DIR_ENV_VAR = "CADRUMO_REGISTRY_DISK_CACHE_DIR"
"""Environment variable backing :attr:`~core.config.Settings.cadrumo_registry_disk_cache_dir`."""

# The bundled tree gets a longer fingerprint TTL than a mutable authoring
# tree, but NOT a process-lifetime one: under an editable install (the
# routine development mode) "bundled" resolves to the literal in-tree
# ``src/cadrumo/_data/registry/aeat`` source directory, which can be edited
# live during a session. A TTL that
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


def is_bundled_registry_path(path: Path) -> bool:
    """Whether ``path`` lies inside the package-bundled registry tree.

    Path-containment sibling of :func:`is_bundled_registry_root`, used by the
    per-file fingerprint to decide whether a content digest must be computed:
    the bundled tree is read-only package data that is never rewritten during
    a process's lifetime (the same immutability premise the pytest disk-cache
    predicate and the longer bundled TTL already rely on), so its files keep
    the cheap stat-only fingerprint, while any mutable authoring tree -- the
    only place an in-run rewrite can collide on ``(size, mtime_ns)`` -- pays
    for the content discriminator. ``path`` must already be resolved. Fails
    closed to ``False`` (content-sensitive fingerprinting) on any resources
    boundary failure.
    """
    try:
        return path.is_relative_to(_bundled_registry_root())
    except (ImportError, OSError, ValueError):
        return False


def toml_file_fingerprint(path: Path) -> tuple[str, int, int, str]:
    """Return the ``(path, size, mtime_ns, content_digest)`` fingerprint for one registry TOML.

    The shared per-file fingerprint primitive behind the loader's cache keys
    and the convenio treaty fingerprints. ``(size, mtime_ns)`` alone cannot
    distinguish two successive writes that produce content of the same byte
    length within the filesystem's effective mtime resolution (coarse on CI
    overlay/network filesystems), so a stat-only fingerprint would serve a
    stale compiled registry after such an edit -- violating the
    complete-tree-fingerprint invariant of the registry authority flow. The
    content digest closes that hole; the stat fields remain as the cheap
    first-order discriminator.

    The package-bundled tree is exempt (empty digest): it is read-only package
    data never rewritten during a process's lifetime -- the same immutability
    premise the pytest disk-cache predicate and the longer bundled TTL already
    encode (:func:`is_bundled_registry_path`) -- and hashing its ~16.5k TOML
    files (~25 MB) would add ~1.3 s to every cold fingerprint walk for a tree
    that cannot exhibit the collision.
    """
    try:
        stat = path.stat()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry TOML could not be fingerprinted; retry after concurrent registry writes settle: {exc}",
        ) from exc
    return str(path), stat.st_size, stat.st_mtime_ns, _toml_content_digest(path)


def _toml_content_digest(path: Path) -> str:
    """Return the mutable-tree content discriminator, or ``""`` for bundled files."""
    if is_bundled_registry_path(path):
        return ""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RegistryLoadError(
            f"{path}: registry TOML could not be fingerprinted; retry after concurrent registry writes settle: {exc}",
        ) from exc
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def _running_under_pytest() -> bool:
    """Whether the current process is a pytest run (including collection and xdist workers)."""
    import os
    import sys

    return (
        "pytest" in sys.modules
        or "PYTEST_CURRENT_TEST" in os.environ
        or "PYTEST_XDIST_WORKER" in os.environ
        or "PYTEST_VERSION" in os.environ
    )


def registry_disk_cache_enabled(*, is_bundled: bool = False) -> bool:
    """Whether the cross-process ``/tmp`` registry pickle is read/written.

    Production (no pytest markers present at all) always keeps the disk
    cache: it loads the registry once at startup with no concurrent edits.

    Under pytest, including collection before ``PYTEST_CURRENT_TEST`` is
    set, the cache is enabled ONLY for ``is_bundled=True`` -- the
    package-bundled, read-only registry tree (:func:`is_bundled_registry_root`).
    That tree is never mutated during a test run, so every pytest-xdist
    worker and every subprocess-spawning test may safely share ONE compiled
    pickle keyed by a content fingerprint of that tree, collapsing what would
    otherwise be an independent multi-second cold compile per worker/subprocess
    into a single shared compile the rest read.

    A mutable or synthetic root (e.g. a test's ``tmp_path`` registry, or any
    path that is not the resolved bundled root) always keeps the cache
    disabled under pytest -- this is the #44 isolation fix: such a root CAN be
    edited mid-run by the very test that built it, and the pickle is keyed by
    file mtime, so sharing it across workers could serve a stale or
    transiently-inconsistent compiled registry (the M303-2009 flake #44
    diagnosed). Only the always-immutable bundled tree is exempt from that
    race.
    """
    if _running_under_pytest():
        return is_bundled
    return True


def registry_disk_cache_dir() -> Path:
    """Return the directory the cross-process registry disk pickle lives in.

    Resolution precedence:

    1. An explicit :attr:`~core.config.Settings.cadrumo_registry_disk_cache_dir`
       (the ``CADRUMO_REGISTRY_DISK_CACHE_DIR`` env var) always wins. A test
       that needs to assert EXCLUSIVE state on the pickle (e.g. "exactly one
       file exists", "the mtime is unchanged") sets this to a test-owned
       directory, so its assertions are not confused by sibling pytest-xdist
       workers touching the shared bundled-root pickle -- while still
       exercising the real filesystem and read/write path. It rides the env
       var (not a monkeypatch) so it also propagates to a subprocess a test
       spawns via ``env=``.
    2. Production (not under pytest) derives
       ``<cadrumo_local_storage_root>/cache/registry`` -- one per-user location
       under the single storage root, never the shared OS temp directory that
       any two host users could collide in.
    3. Under pytest with no explicit override, the cross-worker bundled-root
       share stays in the host-shared OS temp directory: xdist workers each
       get a per-pid ``cadrumo_local_storage_root``, so deriving from it would
       give every worker a private cache and defeat the single-compile sharing
       the disk pickle exists to deliver. The bundled tree is immutable during
       a run, so one host-shared compiled pickle is safe to share.
    """
    settings = load_settings()
    return _resolve_registry_disk_cache_dir(
        override=settings.cadrumo_registry_disk_cache_dir,
        under_pytest=_running_under_pytest(),
        storage_root=settings.cadrumo_local_storage_root,
    )


def _resolve_registry_disk_cache_dir(*, override: Path | None, under_pytest: bool, storage_root: Path) -> Path:
    """Pure resolution of the registry disk-cache directory.

    Split from :func:`registry_disk_cache_dir` so the three branches (explicit
    override, pytest host-shared temp, production storage-root derivation) are
    exercised with real inputs rather than by manipulating the ambient process.
    """
    if override is not None:
        return override
    if under_pytest:
        return Path(tempfile.gettempdir())
    return storage_root / "cache" / "registry"


def registry_disk_cache_max_entries() -> int:
    """Return the retained-pickle ceiling for registry disk-cache eviction.

    Reads :attr:`~core.config.Settings.cadrumo_registry_disk_cache_max_entries`;
    the loader prunes the oldest pickles beyond this count after each write.
    """
    return load_settings().cadrumo_registry_disk_cache_max_entries
