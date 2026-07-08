"""Production modules must obtain UTC time via :func:`~core.time.now`.

No production module under ``src/aeat/`` may call ``datetime.now(UTC)``
or ``datetime.now(tz=UTC)`` inline. All call-sites delegate to the public
:mod:`~core.time` clock facade so the production clock is uniform, traceable,
and compatible with :func:`~core.time.frozen_clock` replay.

The permanent exclusions are test infrastructure and the canonical
implementation module itself. Conditional defaults of the shape
``if now is not None else datetime.now(...)`` remain permitted only on
constructor/helper signatures that already accept an injectable clock argument
named ``now``.

See Also:
    :mod:`~core.time`
        Canonical wall-clock facade and deterministic replay seam.
    :mod:`~tests._inventory`
        Shared production AST inventory surface used by this ratchet.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_AEAT
_CLOCK_MODULE = _SRC_ROOT / "core" / "time" / "_clock.py"
_TEST_INFRA_MODULES: frozenset[Path] = frozenset(
    {
        _SRC_ROOT / "adapters" / "persistence" / "storage" / "envelope" / "_repository_test_suite.py",
        _SRC_ROOT / "tests" / "secure_sql.py",
    },
)

def _is_excluded(path: Path) -> bool:
    if path in _TEST_INFRA_MODULES:
        return True
    try:
        path.relative_to(_CLOCK_MODULE.parent)
        return path.name == _CLOCK_MODULE.name
    except ValueError:
        return False


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_utc_name(node: ast.AST) -> bool:
    return leaf_name(node) == "UTC"


def _is_datetime_now_utc_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "now":
        return False
    if leaf_name(node.func.value) != "datetime":
        return False
    if node.args and _is_utc_name(node.args[0]):
        return True
    return any(keyword.arg == "tz" and _is_utc_name(keyword.value) for keyword in node.keywords)


def _is_now_is_not_none_test(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "now"
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.IsNot)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value is None
    )


def _enclosing_function_accepts_now(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    current: ast.AST | None = node
    while current is not None:
        parent = parents.get(current)
        if isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef):
            return any(arg.arg == "now" for arg in [*parent.args.args, *parent.args.kwonlyargs])
        current = parent
    return False


def _is_documented_now_fallback(node: ast.AST, parents: Mapping[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    return (
        isinstance(parent, ast.IfExp)
        and parent.orelse is node
        and _is_now_is_not_none_test(parent.test)
        and _enclosing_function_accepts_now(parent, parents)
    )


def _collect_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline clock call."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        parents = _parent_map(tree)
        for node in ast.walk(tree):
            if _is_datetime_now_utc_call(node) and not _is_documented_now_fallback(node, parents):
                violations.append(f"{repo_relative(path)}:{node.lineno}")
    return violations


def test_no_inline_datetime_now_utc(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Production modules MUST route UTC time through :func:`~core.time.now`."""
    violations = _collect_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline datetime.now(UTC) call(s) outside the canonical clock module:\n  {joined}\n\n"
            "Replace each call with now() from aeat.core.time. The only permitted\n"
            "inline pattern is the documented escape hatch:\n"
            "    timestamp = now if now is not None else datetime.now(UTC)\n"
            "on signatures that already accept an injectable ``now`` argument.",
        )
