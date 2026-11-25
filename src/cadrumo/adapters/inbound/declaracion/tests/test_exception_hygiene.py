"""Exception-handling hygiene tests for inbound PDF parsing modules."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping, Sequence
from functools import cache
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....tests.exception_hygiene_scan import (
    bare_excepts,
    broad_handlers_without_raise_or_log,
    contextlib_suppress_uses,
    swallowed_with_pass,
)
from .....tests.inventory import ast_for_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

#: The declaracion package, not this tests directory. `Path(__file__).parent`
#: named `declaracion/tests`, whose only non-test files are excluded by the
#: filter below, so the sweep was effectively empty -- and `_PDF_PACKAGE`, being
#: derived from it, resolved to `declaracion/pdf`, which does not exist. The
#: inbound PDF adapter is a SIBLING. Five exception-hygiene assertions covered
#: neither package.
_DECLARACION_PACKAGE = Path(__file__).resolve().parent.parent
_PDF_PACKAGE = _DECLARACION_PACKAGE.parent / "pdf"


@cache
def _production_modules() -> tuple[Path, ...]:
    """Return the production modules every assertion in this module sweeps.

    Floored and root-checked. Each of the five gates below has the shape
    ``assert offenders == []`` over this corpus, so an empty sweep reports the
    same green as a clean one: a moved or renamed package would disarm all
    five at once and say nothing. `require_root=True` turns a missing package
    into a raise instead of an empty tuple, and the count is asserted because
    a package that exists but yields no module is the same blindness.
    """
    packages = (_DECLARACION_PACKAGE, _PDF_PACKAGE)
    modules = tuple(
        sorted(
            path
            for package in packages
            for path in scan_directory(package, pattern="*.py", require_root=True)
            if not path.name.startswith("test_") and path.name != "conftest.py"
        ),
    )
    if not modules:
        message = (
            f"the exception-hygiene sweep reached no production module under {packages}; "
            "a scan matching nothing cannot find a broad except, a bare suppress, or a swallowed error"
        )
        raise AssertionError(message)
    return modules


def _production_trees(source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[Path, ast.AST], ...]:
    items: list[tuple[Path, ast.AST]] = []
    for path in _production_modules():
        tree = ast_for_path(path, source_tree_ast)
        if tree is not None:
            items.append((path, tree))
    return tuple(items)


def test_inbound_pdf_code_does_not_swallow_exceptions_with_pass(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    assert _offenders(source_tree_ast, swallowed_with_pass) == []


def test_inbound_pdf_code_does_not_use_contextlib_suppress(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    assert _offenders(source_tree_ast, contextlib_suppress_uses) == []


def test_inbound_pdf_code_does_not_use_bare_except(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    assert _offenders(source_tree_ast, bare_excepts) == []


def test_inbound_pdf_broad_exception_handlers_raise_or_log(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    assert _offenders(source_tree_ast, broad_handlers_without_raise_or_log) == []


def test_inbound_pdf_code_does_not_read_environment_directly(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    offenders: list[str] = []
    for path, tree in _production_trees(source_tree_ast):
        for node in ast.walk(tree):
            if _is_os_environ_reference(node) or _is_getenv_call(node):
                offenders.append(_location(path, node))

    assert offenders == []


def _offenders(
    source_tree_ast: Mapping[Path, ast.AST], scan: Callable[[ast.AST], Sequence[ast.stmt | ast.excepthandler]]
) -> list[str]:
    return [_location(path, node) for path, tree in _production_trees(source_tree_ast) for node in scan(tree)]


def _location(path: Path, node: ast.AST) -> str:
    try:
        relative = path.relative_to(_DECLARACION_PACKAGE.parent)
    except ValueError:
        relative = path
    line_number = getattr(node, "lineno", None)
    assert isinstance(line_number, int)
    return f"{relative}:{line_number}"


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
