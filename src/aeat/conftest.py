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
import contextlib
import tempfile
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
from .tests import package_python_files, prime_ast_cache

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

    Also primes the shared process-level AST cache
    (``tests._inventory.prime_ast_cache``) so a ratchet that calls
    ``ast_for_path(path)`` WITHOUT threading this fixture through its own
    helpers (the historical bypass pattern -- a ratchet imports only
    ``ast_for_path`` and re-parses independently) still reuses this parse
    instead of re-reading and re-parsing the file from disk.
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
    prime_ast_cache(cache)
    return cache


@pytest.fixture(scope="session")
def source_tree_node_index(
    source_tree_ast: Mapping[Path, ast.AST],
) -> Mapping[type[ast.AST], tuple[tuple[Path, ast.AST], ...]]:
    """Walk every parsed tree ONCE per session, bucketed by concrete AST node type.

    ``source_tree_ast`` amortises the PARSE; it does not amortise the WALK. A
    ratchet that consumes ``source_tree_ast`` and then runs its own
    ``for node in ast.walk(tree): if isinstance(node, X): ...`` still re-walks
    every one of the ~3,300 parsed trees independently. This fixture performs
    that full-tree walk exactly once per session and buckets every node by its
    concrete ``type(node)``, so a ratchet that wants e.g. every ``ast.Call``
    site reads ``source_tree_node_index[ast.Call]`` -- a plain list filter --
    instead of re-walking every tree itself.

    Not every ratchet is a drop-in candidate: a ratchet whose logic correlates
    MULTIPLE node types within a single per-file traversal (parent/child
    order, running per-file state such as "has this function's body already
    bound a ``monkeypatch`` parameter") needs the tree's own nesting context,
    not a flattened per-type bucket, to preserve its exact semantics. Those
    ratchets should keep consuming ``source_tree_ast`` directly. This index is
    the right fit for ratchets whose predicate depends only on one node (or a
    small closed set of node types) in isolation -- most inventory-style
    ratchets in this suite (cast-rationale, Any-parameter-rationale,
    decimal-literal, UTC-validator, and similar single-shape scans).

    Measured: migrating a SINGLE ratchet onto this index (the
    Any-parameter-rationale ratchet, as a trial) increased total suite time --
    the full-tree walk this fixture performs is pure overhead until enough
    ratchets share it to outweigh the one extra walk. Adopt this index only by
    migrating a batch of ratchets together in the same change, verified by
    before/after timing, not one file at a time.
    """
    index: dict[type[ast.AST], list[tuple[Path, ast.AST]]] = {}
    for path, tree in source_tree_ast.items():
        for node in ast.walk(tree):
            index.setdefault(type(node), []).append((path, node))
    return {node_type: tuple(entries) for node_type, entries in index.items()}


@pytest.fixture(scope="session", autouse=True)
def _isolate_registry_caches() -> Iterator[None]:
    """Isolate the registry loader caches per pytest session (the #44 fix).

    The loader's cross-process ``/tmp`` ``aeat_registry_*.pkl`` disk pickle is
    keyed by file mtime and shared across pytest-xdist worker processes, so a
    parallel ``-n`` run could serve a stale/transient compiled registry from one
    worker to another (the #44 isolation gap). The loader now skips that disk
    pickle under pytest; this fixture additionally clears the in-process caches at
    session start and end (the per-process ``lru_cache`` and the 1-second-TTL
    fingerprint cache) and removes any stale ``aeat_registry_*.pkl`` left by a
    prior non-pytest run, so the registry suite is deterministic regardless of
    leftover state.
    """
    from .domain.calculations.registry import clear_fingerprint_cache
    from .domain.calculations.registry._loader import _load_registry_tree_cached

    def _reset(*, purge_disk: bool) -> None:
        _load_registry_tree_cached.cache_clear()
        clear_fingerprint_cache()
        if purge_disk:
            for stale in Path(tempfile.gettempdir()).glob("aeat_registry_*.pkl"):
                with contextlib.suppress(OSError):
                    stale.unlink()

    _reset(purge_disk=True)
    yield
    _reset(purge_disk=False)
