"""Keep package namespaces inert and prevent lazy-facade regressions.

A namespace that serves names through ``__getattr__`` or re-exports another
module is not a defining surface: it hides the dependency from the import graph
and makes ownership depend on import order. This gate scans shipped packages
and the shared test package so the rule applies equally to tests and product
code.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path("src/cadrumo")
_TESTS_INIT = _SRC / "tests" / "__init__.py"


def _module_getattr(tree: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return a module-level ``__getattr__`` definition, if one exists."""
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == "__getattr__":
            return node
    return None


def _shipped_modules() -> list[Path]:
    """Return every module shipped outside a test tree."""
    return [
        path
        for path in scan_directory(_SRC, pattern="*.py", recursive=True)
        if "tests" not in path.parts and "__pycache__" not in path.parts and not path.name.startswith("test_")
    ]


def test_no_shipped_module_resolves_a_name_through_getattr() -> None:
    """A shipped module may not expose names through PEP 562 dispatch."""
    shipped = _shipped_modules()
    assert len(shipped) > 500, "the shipped-module scan found almost nothing; it would pass vacuously"

    offenders = [
        f"{path.as_posix()}:{node.lineno}"
        for path in shipped
        if (node := _module_getattr(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))) is not None
    ]
    assert offenders == [], (
        "these shipped modules resolve names through a module-level __getattr__, "
        "which hides the defining module from consumers:\n" + "\n".join(f"  {entry}" for entry in offenders)
    )


def test_shared_test_namespace_is_inert() -> None:
    """The shared test package exposes no names and has no lazy dispatch."""
    tree = ast.parse(_TESTS_INIT.read_text(encoding="utf-8"), filename=str(_TESTS_INIT))
    assert _module_getattr(tree) is None
    assert not any(isinstance(node, ast.Import | ast.ImportFrom) for node in tree.body)

    all_assignments = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign | ast.AnnAssign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        )
    ]
    assert len(all_assignments) == 1
    value = all_assignments[0]
    assert isinstance(value, ast.Tuple | ast.List) and not value.elts
