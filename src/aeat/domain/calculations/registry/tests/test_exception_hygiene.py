"""Exception-handling hygiene tests for registry production modules."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from .....tests import ast_for_path, non_test_python_files_under

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_REGISTRY_PACKAGE = Path(__file__).resolve().parents[1]


def _production_modules() -> tuple[Path, ...]:
    return non_test_python_files_under(_REGISTRY_PACKAGE)


def _production_trees(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    items: list[tuple[Path, ast.AST]] = []
    for path in _production_modules():
        tree = ast_for_path(path, source_tree_ast)
        if tree is not None:
            items.append((path, tree))
    return tuple(items)


def test_registry_production_code_does_not_swallow_exceptions_with_pass(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """A caught exception must be handled, converted, logged, or re-raised."""

    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                offenders.append(_location(path, node))

    assert offenders == []


def test_registry_production_code_does_not_use_contextlib_suppress(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Suppressing exceptions hides registry drift; use an explicit typed result."""

    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            for item in node.items:
                context_expr = item.context_expr
                if isinstance(context_expr, ast.Call):
                    context_expr = context_expr.func
                if isinstance(context_expr, ast.Attribute) and context_expr.attr == "suppress":
                    offenders.append(_location(path, node))
                if isinstance(context_expr, ast.Name) and context_expr.id == "suppress":
                    offenders.append(_location(path, node))

    assert offenders == []


def test_registry_production_code_does_not_use_bare_except(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Registry code must name the exception class it is prepared to handle."""

    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                offenders.append(_location(path, node))

    assert offenders == []


def test_registry_production_broad_exception_handlers_raise_or_log(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Broad exception handlers must preserve failure visibility."""

    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler) or node.type is None:
                continue
            if not _is_broad_exception_type(node.type):
                continue
            has_raise = any(isinstance(child, ast.Raise) for child in ast.walk(node))
            has_log = any(_is_logging_call(child) for child in ast.walk(node))
            if not has_raise and not has_log:
                offenders.append(_location(path, node))

    assert offenders == []


def _location(path: Path, node: ast.AST) -> str:
    relative = path.relative_to(_REGISTRY_PACKAGE)
    return f"{relative}:{node.lineno}"


def _is_broad_exception_type(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"Exception", "BaseException"}
    if isinstance(node, ast.Tuple):
        return any(_is_broad_exception_type(item) for item in node.elts)
    return False


def _is_logging_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    return node.func.attr in {"debug", "info", "warning", "error", "exception", "critical"}
