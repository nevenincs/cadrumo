"""Package-level pytest fixtures for every test under ``src/aeat/``.

Hosts the ``source_tree_ast`` session-scoped fixture that ratchet
inventories consume to amortise the AST parse cost across the suite.
The fixture has to live here (not in ``src/aeat/tests/conftest.py``)
because pytest's conftest discovery walks UP from each test file; a
conftest inside the ``tests/`` subdirectory is invisible to ratchets
hosted at ``src/aeat/test_*.py`` and elsewhere under ``src/aeat/``.

Marker-contract and live-import gating remain hosted from
``src/aeat/tests/conftest.py`` (collection-time hook scope is shared
across all child conftests by pytest).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

# Force wizard-catalogue registration at conftest import time so every
# pytest worker process has SETUP_FLOW / WIZARD_FLOWS registered before
# any test runs. Otherwise a cli_runner.invoke path that opens a profile
# session (short-circuiting the CLI bootstrap's catalogue registration at
# entrypoints/cli/__init__.py:281) and doesn't transitively import the
# wizard package hits the "Wizard catalogue has not been registered"
# guard. Documented in #158 entry 2 and ADR pending under
# session-honest-followups P03.S19.
from .core.external_constants import UTF_8_ENCODING
from .tests import package_python_files

_SRC_AEAT_ROOT: Path = Path(__file__).resolve().parent
"""Root of the ``src/aeat/`` source tree (the directory hosting this conftest)."""


@pytest.fixture(scope="session")
def source_tree_ast() -> Mapping[Path, ast.AST]:
    """Return a session-cached mapping of every ``src/aeat/`` ``.py`` file to its parsed AST.

    Walks ``src/aeat/`` once per pytest session via ``rglob("*.py")``, skips
    ``__pycache__`` directories, ``.venv`` parents, and the ``_data/``
    payload tree, reads each file as UTF-8 with ``errors='replace'`` (so
    a stray encoding cookie cannot raise), and parses it with the
    standard library ``ast`` module. Files that fail to parse with
    ``SyntaxError`` are silently skipped — the fixture is a best-effort
    cache, not a syntax gate; ratchets that need to surface unparseable
    files should fall back to their own per-test scan.

    Consumers retain their own filter predicates (e.g. ``test_*.py``
    only, or exclude certain subdirs). The fixture is the AST cache;
    the policy is per-test.
    """
    cache: dict[Path, ast.AST] = {}
    for path in package_python_files():
        try:
            source = path.read_text(encoding=UTF_8_ENCODING, errors="replace")
        except OSError:
            continue
        try:
            cache[path] = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
    return cache


@pytest.fixture(scope="session", autouse=True)
def _isolate_registry_caches() -> Iterator[None]:
    """Clear the registry loader's in-process caches per pytest session (the #44 fix).

    The loader's cross-process ``/tmp`` ``aeat_registry_*.pkl`` disk pickle is
    keyed by file mtime and was historically shared across pytest-xdist worker
    processes, so a parallel ``-n`` run could serve a stale/transient compiled
    registry from one worker to another (the #44 isolation gap). The loader
    closes that race at the ROOT: the disk pickle is now read/written under
    pytest only for the package-bundled, read-only registry tree
    (``registry_disk_cache_enabled(is_bundled=...)``), which is never mutated
    mid-run; a mutable/synthetic root (a test's ``tmp_path`` registry) never
    gets a disk pickle under pytest at all, so no per-worker purge is needed to
    protect it.

    This fixture therefore clears only the per-process ``lru_cache`` and the
    1-second-TTL fingerprint cache at session start and end -- it does NOT
    purge the ``/tmp`` disk pickle. An earlier version of this fixture DID
    purge it unconditionally at session start; measured directly (two separate
    ``pytest`` invocations against the same bundled-tree content, each its own
    "session" exactly as an xdist worker's own session boundary is), that
    purge deleted the very pickle the bundled-root cache had just written,
    forcing every subsequent session/worker to independently recompile the
    bundled tree from scratch (8.6s-8.7s per invocation, zero cross-session
    reuse) -- silently defeating the cross-worker sharing the disk-cache fix
    exists to deliver. The disk-cache read path is already self-validating (a
    SHA-256 of the schema version plus every file's path/size/mtime), so a
    stale or incompatible pickle simply misses on its own; no defensive purge
    is needed for correctness, only for tidiness the temp directory does not
    require.
    """
    from .domain.calculations.registry import clear_fingerprint_cache
    from .domain.calculations.registry._loader import _load_registry_tree_cached

    def _reset() -> None:
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()

    _reset()
    yield
    _reset()
