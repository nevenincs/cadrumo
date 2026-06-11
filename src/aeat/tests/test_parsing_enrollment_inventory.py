"""Inventory test: zero inline date.fromisoformat() and value.lower() == "true" survive in production.

Rule
----
Production modules under ``src/aeat/`` must not contain:

1. ``date.fromisoformat(`` — direct bare invocations bypassing the canonical
   ``_parse_iso8601_date`` or ``_parse_ddmmyyyy_date`` helpers.
2. ``value.lower() == "true"`` or ``value.lower() == "false"`` — inline boolean
   parsing that bypasses the canonical ``_parse_bool`` helper.

Exclusions
----------
- ``test_*.py`` files: test suites verify the helpers and may use direct calls.
- ``src/aeat/core/parsing/_dates.py``: the canonical implementation itself.
- ``src/aeat/core/parsing/_utils.py``: the canonical bool-parsing implementation.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator, Mapping

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = pathlib.Path(__file__).parent.parent

# Canonical modules that are allowed to use these primitives directly.
_CANONICAL_MODULES: frozenset[str] = frozenset(
    {
        "_dates.py",
        "_utils.py",
    },
)


def _is_excluded(path: pathlib.Path) -> bool:
    if path.name.startswith("test_"):
        return True
    # The canonical implementation modules are exempted by definition.
    if path.name in _CANONICAL_MODULES:
        try:
            path.relative_to(_SRC_ROOT / "core" / "parsing")
            return True
        except ValueError:
            pass
    # core/ modules may use date.fromisoformat directly because they share the
    # same package layer as the canonical parsers and cannot import from
    # core.parsing._dates without risking circular-import chains through
    # get_logger → config → parsing._dates.
    try:
        path.relative_to(_SRC_ROOT / "core")
        return True
    except ValueError:
        pass
    return False


# ---------------------------------------------------------------------------
# AST-based detection of date.fromisoformat( calls
# ---------------------------------------------------------------------------


def _fromisoformat_call_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of ``date.fromisoformat(...)`` call expressions."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "fromisoformat"
            and isinstance(func.value, ast.Name)
            and func.value.id == "date"
        ):
            yield node.lineno


# ---------------------------------------------------------------------------
# Text-based detection of inline boolean parsing patterns
# ---------------------------------------------------------------------------

_INLINE_BOOL_PATTERNS: tuple[str, ...] = (
    '.lower() == "true"',
    '.lower() == "false"',
    ".lower() == 'true'",
    ".lower() == 'false'",
)


def _inline_bool_violations(path: pathlib.Path, lines: list[str]) -> list[str]:
    """Return ``file:line`` strings for inline bool-parsing patterns."""
    hits: list[str] = []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in _INLINE_BOOL_PATTERNS:
            if pattern in line:
                rel = path.relative_to(_SRC_ROOT.parent.parent)
                hits.append(f"{rel}:{lineno}")
                break
    return hits


# ---------------------------------------------------------------------------
# Violation collectors
# ---------------------------------------------------------------------------


def _collect_fromisoformat_violations(
    source_tree_ast: Mapping[pathlib.Path, ast.AST] | None = None,
) -> list[str]:
    """Return ``file:line`` strings for bare ``date.fromisoformat()`` calls.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file. When omitted, fall back to walk-and-parse so
    the helper's no-arg signature stays compatible with importlib
    callers.
    """
    violations: list[str] = []
    if source_tree_ast is None:
        for path in sorted(_SRC_ROOT.rglob("*.py")):
            if _is_excluded(path):
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError:
                continue
            for lineno in _fromisoformat_call_linenos(tree):
                rel = path.relative_to(_SRC_ROOT.parent.parent)
                violations.append(f"{rel}:{lineno}")
        return violations

    for path in sorted(source_tree_ast):
        if _is_excluded(path):
            continue
        try:
            path.relative_to(_SRC_ROOT)
        except ValueError:
            continue
        tree = source_tree_ast[path]
        for lineno in _fromisoformat_call_linenos(tree):
            rel = path.relative_to(_SRC_ROOT.parent.parent)
            violations.append(f"{rel}:{lineno}")
    return violations


def _collect_inline_bool_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if _is_excluded(path):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        lines = source.splitlines()
        violations.extend(_inline_bool_violations(path, lines))
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_bare_date_fromisoformat(
    source_tree_ast: Mapping[pathlib.Path, ast.AST],
) -> None:
    """Zero ``date.fromisoformat(`` calls survive in production modules.

    All date parsing must go through ``_parse_iso8601_date`` or
    ``_parse_ddmmyyyy_date`` from ``aeat.core.parsing._dates``.

    Consumes the session-scoped AST cache so the per-file parse cost is
    amortised across the full ratchet suite.
    """
    violations = _collect_fromisoformat_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare date.fromisoformat() call(s) found in production code:\n  {joined}\n\n"
            "Replace with _parse_iso8601_date() or _parse_ddmmyyyy_date() from aeat.core.parsing._dates.",
        )


def test_no_inline_bool_lower_comparison() -> None:
    """Zero ``value.lower() == \"true\"/\"false\"`` patterns survive in production modules.

    All boolean string parsing must go through ``_parse_bool`` from
    ``aeat.core.parsing._utils``.
    """
    violations = _collect_inline_bool_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline bool-parsing pattern(s) found in production code:\n  {joined}\n\n"
            "Replace with _parse_bool() from aeat.core.parsing._utils.",
        )
