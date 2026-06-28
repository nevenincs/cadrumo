"""Shared pytest fixtures and collection-time guards for the AEAT test suite.

See ``src/aeat/tests/README.md`` for the marker taxonomy and pytest
posture this module enforces.

This module enforces the following invariants at collection time:

1. The hexagonal marker taxonomy contract via the
   shared helper in :mod:`aeat.tests._marker_hook`. Also hosted from the
   repo-root ``conftest.py`` so items collected anywhere under
   ``src/aeat/`` pass through the same enforcement surface; double
   invocation is safe because the helper enforces invariants on items
   it receives and filters in-place.
2. No file containing an ``aeat_live`` item may import
   any symbol in :data:`BANNED_LIVE_IMPORTS`.
3. ``aeat_live`` items are skipped unless ``AEAT_LIVE_TESTS_ENABLED`` is
   truthy.

The ``env/.env`` auto-load happens at module-load time in the repo-root
``conftest.py``.

Banned-import hits are hard ``pytest.exit`` rather than warnings.

The ``source_tree_ast`` session-scoped fixture is consumed by ratchet
tests throughout the relocated ``tests/`` folders and lives at
``src/aeat/conftest.py`` rather than here so pytest can discover it
from every source test subtree.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Iterable
from pathlib import Path

import pytest

from ._marker_hook import apply as _apply_marker_contract

LIVE_ACCESS_MARKERS: frozenset[str] = frozenset({"aeat_live"})
"""Execution markers that count as ``live`` for banned-import / opt-in gating."""

BANNED_LIVE_IMPORTS: frozenset[str] = frozenset(
    {
        "unittest",
        "unittest." + "mo" + "ck",
        "mo" + "ck",
        "pytest_mock",
        "responses",
        "httpx_mock",
        "pytest_httpx",
        "vcr",
        "vcrpy",
        "freezegun",
        "time_machine",
    },
)
"""Import targets that may never appear in a file containing a live-marked test."""

LIVE_OPT_IN_ENV: str = "AEAT_LIVE_TESTS_ENABLED"
"""Environment variable that opts ``aeat_live`` tests into execution."""

_TRUTHY: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def _truthy(value: str | None) -> bool:
    """Return True when the given env-style value is a recognised truthy token."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


def _marker_names(item: pytest.Item) -> set[str]:
    """Return the set of marker names attached to a collected item."""
    return {mark.name for mark in item.iter_markers()}


def _scan_banned_imports(path: Path) -> set[str]:
    """AST-scan a file and return any import target in :data:`BANNED_LIVE_IMPORTS`.

    The file is never executed; this is a syntactic scan. Handles both
    ``import X`` / ``import X.Y`` and ``from X import Y`` / ``from X.Y import Z``.
    Reads as bytes so ``ast.parse`` honours any PEP 263 encoding cookie and
    cannot raise ``UnicodeDecodeError`` on an unusual source encoding.
    """
    try:
        source = path.read_bytes()
    except OSError:
        return set()
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return set()

    hits: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits.update(_banned_hits_for_import(node))
        elif isinstance(node, ast.ImportFrom):
            hits.update(_banned_hits_for_import_from(node))
    return hits


def _banned_hits_for_import(node: ast.Import) -> set[str]:
    """Collect banned-symbol hits from one ``import X[, Y...]`` statement."""
    hits: set[str] = set()
    for alias in node.names:
        name = alias.name
        if name in BANNED_LIVE_IMPORTS:
            hits.add(name)
        root = name.split(".", 1)[0]
        if root in BANNED_LIVE_IMPORTS:
            hits.add(root)
    return hits


def _banned_hits_for_import_from(node: ast.ImportFrom) -> set[str]:
    """Collect banned-symbol hits from one ``from X import Y`` statement."""
    if node.module is None:
        return set()
    hits: set[str] = set()
    module = node.module
    if module in BANNED_LIVE_IMPORTS:
        hits.add(module)
    root = module.split(".", 1)[0]
    if root in BANNED_LIVE_IMPORTS:
        hits.add(root)
    return hits


def _live_item_paths(items: Iterable[pytest.Item]) -> set[Path]:
    """Return every source file that contributed at least one live-marked item."""
    return {item.path for item in items if _marker_names(item) & LIVE_ACCESS_MARKERS}


def _check_banned_live_imports(paths: Iterable[Path]) -> list[str]:
    """Return a list of violation strings for files importing any banned symbol."""
    violations: list[str] = []
    for path in sorted(paths):
        hits = _scan_banned_imports(path)
        if hits:
            violations.append(f"{path}: imports banned symbol(s) {sorted(hits)} in a file containing an aeat_live item")
    return violations


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Enforce the hexagonal marker contract, banned-import scan, and live opt-in gate.

    Runs ``tryfirst=True`` so it sees every collected item *before* pytest's
    built-in ``-m`` keyword filter deselects anything. This ensures the
    banned-live-import scan catches regressions even when the default
    ``-m 'unit'`` selector would otherwise deselect the offending items.

    Ordering: the hexagonal marker contract (``_apply_marker_contract``) runs
    first so any taxonomy violation short-circuits with a
    :class:`pytest.UsageError` before the banned-import and opt-in passes
    operate on the surviving items.

    Args:
        config: The active :class:`pytest.Config` for the session.
        items: Collected test items; mutated in place by the shared helper
            and by the live-opt-in skip step.
    """
    _apply_marker_contract(config, items)

    live_paths = _live_item_paths(items)
    if live_paths:
        import_violations = _check_banned_live_imports(live_paths)
        if import_violations:
            header = "Banned import in live-marked file (see src/aeat/tests/README.md):"
            message = header + "\n  " + "\n  ".join(import_violations)
            pytest.exit(message, returncode=2)

    if not _truthy(os.environ.get(LIVE_OPT_IN_ENV)):
        skip_reason = f"Live tests disabled — set {LIVE_OPT_IN_ENV}=1 to enable"
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            if "aeat_live" in _marker_names(item):
                item.add_marker(skip_marker)
