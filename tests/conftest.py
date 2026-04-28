"""Shared pytest fixtures and collection-time guards for the AEAT test suite.

See ``tests/README.md`` and ``.vault/adr/2026-04-17-pytest-markers-adr.md``.

This module enforces the following invariants at collection time:

1. The nine-marker taxonomy contract (access axis + domain axis) via the
   shared helper in :mod:`tests._marker_hook`. Also hosted from the
   repo-root ``conftest.py`` so items collected under ``src/aeat/`` pass
   through the same enforcement surface; double invocation is safe
   because the helper enforces invariants on items it receives and
   filters in-place.
2. No file containing a ``live_read`` or ``live_write`` item may import
   any symbol in :data:`BANNED_LIVE_IMPORTS` (carried over from PR #160).
3. ``live_read`` items are skipped unless ``AEAT_LIVE_TESTS_ENABLED`` is
   truthy; ``live_write`` items are dropped by the shared helper (see
   :mod:`tests._marker_hook`).

The ``env/.env`` auto-load happens at module-load time in the repo-root
``conftest.py`` so both ``tests/`` and ``src/aeat/`` collections share
it.

Banned-import hits are hard ``pytest.exit`` rather than warnings.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Iterable
from pathlib import Path

import pytest

from tests._marker_hook import apply as _apply_marker_contract

LIVE_ACCESS_MARKERS: frozenset[str] = frozenset({"live_read", "live_write"})
"""Access markers that count as ``live`` for banned-import / opt-in gating."""

BANNED_LIVE_IMPORTS: frozenset[str] = frozenset(
    {
        "unittest",
        "unittest.mock",
        "mock",
        "pytest_mock",
        "responses",
        "httpx_mock",
        "pytest_httpx",
        "vcr",
        "vcrpy",
        "freezegun",
        "time_machine",
    }
)
"""Import targets that may never appear in a file containing a live-marked test."""

LIVE_OPT_IN_ENV: str = "AEAT_LIVE_TESTS_ENABLED"
"""Environment variable that opts ``live_read`` tests into execution."""

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
            for alias in node.names:
                name = alias.name
                if name in BANNED_LIVE_IMPORTS:
                    hits.add(name)
                root = name.split(".", 1)[0]
                if root in BANNED_LIVE_IMPORTS:
                    hits.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
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
            violations.append(
                f"{path}: imports banned symbol(s) {sorted(hits)} in a file containing a live_read or live_write item"
            )
    return violations


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Enforce the nine-marker contract, banned-import scan, and live opt-in gate.

    Runs ``tryfirst=True`` so it sees every collected item *before* pytest's
    built-in ``-m`` keyword filter deselects anything. This ensures the
    banned-live-import scan catches regressions even when the default
    ``-m 'unit'`` selector would otherwise deselect the offending items.

    Ordering: the nine-marker contract (``_apply_marker_contract``) runs
    first so any taxonomy violation short-circuits with a
    :class:`pytest.UsageError` and so ``live_write`` items are dropped
    before the banned-import and opt-in passes operate on the surviving
    items.

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
            header = (
                "Banned import in live-marked file "
                "(see tests/README.md and "
                ".vault/adr/2026-04-17-pytest-markers-adr.md):"
            )
            message = header + "\n  " + "\n  ".join(import_violations)
            pytest.exit(message, returncode=2)

    if not _truthy(os.environ.get(LIVE_OPT_IN_ENV)):
        skip_reason = f"Live tests disabled — set {LIVE_OPT_IN_ENV}=1 to enable"
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            if "live_read" in _marker_names(item):
                item.add_marker(skip_marker)

    # #305 cluster H: fixture_tier_l1 / l2 / l3 marker-driven skips.
    _apply_fixture_tier_gates(items)


def _apply_fixture_tier_gates(items: list[pytest.Item]) -> None:
    """Skip fixture_tier tests per environment toggles.

    - ``AEAT_FIXTURE_L2_ENABLED=1`` to opt in to L2 (scrubbed real) tests.
    - ``AEAT_FIXTURE_L3_ONLY=1`` to keep only L3 (synthetic) tests.
    - ``AEAT_FIXTURE_OFFLINE=1`` deselects L1 tests unless the anchor is
      already cached under ``.cache/l1_anchors/`` (the cached case is
      handled by the anchor-loader fixtures themselves; in strict-offline
      mode we simply skip every L1 test to keep CI deterministic).
    """
    l2_enabled = _truthy(os.environ.get("AEAT_FIXTURE_L2_ENABLED"))
    l3_only = _truthy(os.environ.get("AEAT_FIXTURE_L3_ONLY"))
    offline = _truthy(os.environ.get("AEAT_FIXTURE_OFFLINE"))

    skip_l2 = pytest.mark.skip(reason="fixture_tier_l2 disabled; set AEAT_FIXTURE_L2_ENABLED=1")
    skip_l3_only = pytest.mark.skip(reason="AEAT_FIXTURE_L3_ONLY=1: non-L3 tests deselected")
    skip_l1_offline = pytest.mark.skip(reason="AEAT_FIXTURE_OFFLINE=1: L1 tests require network")

    for item in items:
        markers = _marker_names(item)
        if "fixture_tier_l2" in markers and not l2_enabled:
            item.add_marker(skip_l2)
        if "fixture_tier_l1" in markers and offline:
            item.add_marker(skip_l1_offline)
        if l3_only and any(m in markers for m in ("fixture_tier_l1", "fixture_tier_l2")):
            item.add_marker(skip_l3_only)
