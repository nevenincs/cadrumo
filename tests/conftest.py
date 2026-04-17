"""Shared pytest fixtures and collection-time guards for the AEAT test suite.

See ``tests/README.md`` and ``.vault/adr/2026-04-17-pytest-only-testing-adr.md``.

This module enforces three invariants at collection time:

1. Every collected test carries exactly one of ``@pytest.mark.unit`` or
   ``@pytest.mark.live``.
2. No file containing a ``@pytest.mark.live`` item imports any symbol from
   :data:`BANNED_LIVE_IMPORTS`.
3. Live tests are skipped unless ``AEAT_LIVE_TESTS_ENABLED`` is truthy.

All three failures are hard ``pytest.exit`` rather than warnings.
"""

from __future__ import annotations

import ast
import os
from collections.abc import Iterable
from pathlib import Path

import pytest

REQUIRED_MARKERS: frozenset[str] = frozenset({"unit", "live"})
"""Every test must carry exactly one of these markers."""

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
"""Environment variable that opts live tests into execution."""

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
    """AST-scan a file and return any import target that is in :data:`BANNED_LIVE_IMPORTS`.

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
    return {item.path for item in items if "live" in _marker_names(item)}


def _check_markers(items: Iterable[pytest.Item]) -> list[str]:
    """Return a list of violation strings for items lacking exactly one required marker."""
    violations: list[str] = []
    for item in items:
        marks = _marker_names(item) & REQUIRED_MARKERS
        if not marks:
            violations.append(f"{item.nodeid}: missing required marker (one of {sorted(REQUIRED_MARKERS)})")
        elif len(marks) > 1:
            violations.append(f"{item.nodeid}: has more than one of {sorted(REQUIRED_MARKERS)} ({sorted(marks)})")
    return violations


def _check_banned_live_imports(paths: Iterable[Path]) -> list[str]:
    """Return a list of violation strings for files importing any banned symbol."""
    violations: list[str] = []
    for path in sorted(paths):
        hits = _scan_banned_imports(path)
        if hits:
            violations.append(f"{path}: imports banned symbol(s) {sorted(hits)} in a file containing @pytest.mark.live")
    return violations


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Enforce marker discipline, banned-import scan, and live opt-in gating.

    Runs ``tryfirst=True`` so it sees every collected item *before* pytest's
    built-in ``-m`` keyword filter deselects anything. This ensures the
    banned-live-import scan catches regressions even when the default
    ``-m 'not live'`` would otherwise deselect the offending items.

    Args:
        items: Collected test items; mutated in place to add skip markers when
            live tests are not opted in.
    """
    marker_violations = _check_markers(items)
    if marker_violations:
        header = "Marker discipline violated (every test must be @pytest.mark.unit XOR @pytest.mark.live):"
        message = header + "\n  " + "\n  ".join(marker_violations)
        pytest.exit(message, returncode=2)

    live_paths = _live_item_paths(items)
    if live_paths:
        import_violations = _check_banned_live_imports(live_paths)
        if import_violations:
            header = (
                "Banned import in live-marked file "
                "(see tests/README.md and "
                ".vault/adr/2026-04-17-pytest-only-testing-adr.md):"
            )
            message = header + "\n  " + "\n  ".join(import_violations)
            pytest.exit(message, returncode=2)

    if not _truthy(os.environ.get(LIVE_OPT_IN_ENV)):
        skip_reason = f"Live tests disabled — set {LIVE_OPT_IN_ENV}=1 to enable"
        skip_marker = pytest.mark.skip(reason=skip_reason)
        for item in items:
            if "live" in _marker_names(item):
                item.add_marker(skip_marker)
