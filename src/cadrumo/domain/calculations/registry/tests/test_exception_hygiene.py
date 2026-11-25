"""Exception-handling hygiene tests for registry production modules."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import pytest

from .....tests.exception_hygiene_scan import (
    bare_excepts,
    broad_handlers_without_raise_or_log,
    contextlib_suppress_uses,
    swallowed_with_pass,
)
from .....tests.inventory import ast_for_path, non_test_python_files_under

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


def test_registry_production_code_does_not_swallow_exceptions_with_pass(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """A caught exception must be handled, converted, logged, or re-raised."""

    assert _offenders(source_tree_ast, swallowed_with_pass) == []


def test_registry_production_code_does_not_use_contextlib_suppress(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Suppressing exceptions hides registry drift; use an explicit typed result."""

    assert _offenders(source_tree_ast, contextlib_suppress_uses) == []


def test_registry_production_code_does_not_use_bare_except(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Registry code must name the exception class it is prepared to handle."""

    assert _offenders(source_tree_ast, bare_excepts) == []


def test_registry_production_broad_exception_handlers_raise_or_log(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Broad exception handlers must preserve failure visibility."""

    assert _offenders(source_tree_ast, broad_handlers_without_raise_or_log) == []


def _offenders(
    source_tree_ast: Mapping[Path, ast.AST], scan: Callable[[ast.AST], Sequence[ast.stmt | ast.excepthandler]]
) -> list[str]:
    return [_location(path, node) for path, tree in _production_trees(source_tree_ast) for node in scan(tree)]


def _location(path: Path, node: ast.AST) -> str:
    relative = path.relative_to(_REGISTRY_PACKAGE)
    lineno = getattr(node, "lineno", None)
    assert isinstance(lineno, int)
    return f"{relative}:{lineno}"
