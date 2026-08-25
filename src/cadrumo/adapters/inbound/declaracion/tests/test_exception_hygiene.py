"""Exception-handling hygiene tests for inbound PDF parsing modules."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from functools import cache
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....tests import ast_for_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_DECLARACION_PACKAGE = Path(__file__).parent
_PDF_PACKAGE = _DECLARACION_PACKAGE.parent / "pdf"


@cache
def _production_modules() -> tuple[Path, ...]:
    packages = (_DECLARACION_PACKAGE, _PDF_PACKAGE)
    return tuple(
        sorted(
            path
            for package in packages
            for path in scan_directory(package, pattern="*.py")
            if not path.name.startswith("test_") and path.name != "conftest.py"
        ),
    )


def _production_trees(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    items: list[tuple[Path, ast.AST]] = []
    for path in _production_modules():
        tree = ast_for_path(path, source_tree_ast)
        if tree is not None:
            items.append((path, tree))
    return tuple(items)


def test_inbound_pdf_code_does_not_swallow_exceptions_with_pass(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                offenders.append(_location(path, node))

    assert offenders == []


def test_inbound_pdf_code_does_not_use_contextlib_suppress(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if not isinstance(node, ast.With):
                continue
            for item in node.items:
                context_expr = item.context_expr
                if isinstance(context_expr, ast.Call):
                    context_expr = context_expr.func
                if _is_suppress_reference(context_expr):
                    offenders.append(_location(path, node))

    assert offenders == []


def test_inbound_pdf_code_does_not_use_bare_except(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                offenders.append(_location(path, node))

    assert offenders == []


def test_inbound_pdf_broad_exception_handlers_raise_or_log(source_tree_ast: Mapping[Path, ast.AST]) -> None:
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


def test_inbound_pdf_code_does_not_read_environment_directly(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if _is_os_environ_reference(node) or _is_getenv_call(node):
                offenders.append(_location(path, node))

    assert offenders == []


def _location(path: Path, node: ast.AST) -> str:
    try:
        relative = path.relative_to(_DECLARACION_PACKAGE.parent)
    except ValueError:
        relative = path
    line_number = getattr(node, "lineno", None)
    assert isinstance(line_number, int)
    return f"{relative}:{line_number}"


def _is_suppress_reference(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "suppress"
    if isinstance(node, ast.Name):
        return node.id == "suppress"
    return False


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


def _is_os_environ_reference(node: ast.AST) -> bool:
    if not isinstance(node, ast.Attribute) or node.attr != "environ":
        return False
    return isinstance(node.value, ast.Name) and node.value.id == "os"


def _is_getenv_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "getenv":
        return isinstance(func.value, ast.Name) and func.value.id == "os"
    return isinstance(func, ast.Name) and func.id == "getenv"
