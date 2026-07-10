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

See Also:
    :mod:`~tests._inventory`
        Provides the shared production AST inventory used by this parsing
        enrollment gate.
    :func:`~core.parsing.parse_iso8601_date`
        Public ISO date parser that production callers should use instead of
        direct ``date.fromisoformat`` calls.
    :func:`~core.parsing.parse_ddmmyyyy_date`
        Public Spanish day-first parser for Sede and form-input dates.
    :func:`~core.parsing.parse_bool`
        Public boolean-token parser that replaces inline lower-case string
        comparisons.

Date, day-first, and boolean parsing must funnel through one canonical helper
each, so a locale or format quirk is fixed in exactly one place.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_AEAT

# Canonical modules that are allowed to use these primitives directly.
_CANONICAL_MODULES: frozenset[str] = frozenset(
    {
        "_dates.py",
        "_utils.py",
    },
)


def _is_excluded(path: Path) -> bool:
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
# Violation collectors
# ---------------------------------------------------------------------------


def _is_lower_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "lower"
        and not node.args
        and not node.keywords
    )


def _is_bool_literal(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value in {"true", "false"}


def _inline_bool_linenos(tree: ast.AST) -> Iterator[int]:
    """Yield line numbers of ``value.lower() == "true"/"false"`` comparisons."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if len(node.ops) != 1 or not isinstance(node.ops[0], ast.Eq):
            continue
        if len(node.comparators) != 1:
            continue
        if (_is_lower_call(node.left) and _is_bool_literal(node.comparators[0])) or (
            _is_bool_literal(node.left) and _is_lower_call(node.comparators[0])
        ):
            yield node.lineno


def _collect_fromisoformat_violations(
    source_tree_ast: Mapping[Path, ast.AST] | None = None,
) -> list[str]:
    """Return ``file:line`` strings for bare ``date.fromisoformat()`` calls.

    When *source_tree_ast* is supplied (test path), consume the cached
    parsed AST per file. When omitted, fall back to walk-and-parse so
    the helper's no-arg signature stays compatible with importlib
    callers.
    """
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for lineno in _fromisoformat_call_linenos(tree):
            violations.append(f"{repo_relative(path)}:{lineno}")
    return violations


def _collect_inline_bool_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for lineno in _inline_bool_linenos(tree):
            violations.append(f"{repo_relative(path)}:{lineno}")
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_bare_date_fromisoformat(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Zero ``date.fromisoformat(`` calls survive in production modules.

    All date parsing must go through ``_parse_iso8601_date`` or
    ``_parse_ddmmyyyy_date`` from ``aeat.core.parsing._dates``.

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations = _collect_fromisoformat_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare date.fromisoformat() call(s) found in production code:\n  {joined}\n\n"
            "Replace with _parse_iso8601_date() or _parse_ddmmyyyy_date() from aeat.core.parsing._dates.",
        )


def test_no_inline_bool_lower_comparison(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Zero ``value.lower() == \"true\"/\"false\"`` patterns survive in production modules.

    All boolean string parsing must go through ``_parse_bool`` from
    ``aeat.core.parsing._utils``.
    """
    violations = _collect_inline_bool_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline bool-parsing pattern(s) found in production code:\n  {joined}\n\n"
            "Replace with _parse_bool() from aeat.core.parsing._utils.",
        )
