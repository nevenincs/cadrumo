"""Boundary checks that protect :mod:`~core` from upward dependencies.

The :mod:`~core` package sits at the bottom of the dependency
graph: the outer layers (:mod:`~adapters`, :mod:`~application`,
:mod:`~domain`, :mod:`~entrypoints`) depend on it, never the
other way round. The tests here parse every production module under
:mod:`~core` and assert that none of them imports anything from
those outer packages at *import time*.

Import-time coupling is what the layered architecture forbids: a
module-level ``import`` of an outer package would make loading
:mod:`~core` drag the outer layer in, opening the door to import
cycles and layer inversion. Two import forms are deliberately *not*
import-time edges and are excluded from the scan, matching the
authoritative ``core-not-outer`` import-linter contract
(``exclude_type_checking_imports = True``):

* ``TYPE_CHECKING``-guarded imports — evaluated only by static type
  checkers, never at runtime.
* Function- and method-scoped (deferred) imports — evaluated only when
  the enclosing callable runs. ``aeat.core`` uses this pattern
  deliberately (for example :mod:`~core.config` and the resource
  repositories) so a core primitive can call into a higher layer
  lazily without a load-time dependency.

A second test guards against the re-introduction of the historical
``WorkspaceLockedError`` symbol that was removed during the
storage-foundation cleanup.

See Also:
    :func:`~tests._inventory.production_ast_items`
        Shared AST inventory used to scan production modules for import-time
        layer inversions.
    :func:`~tests._inventory.production_python_files`
        Production source inventory used by the removed-symbol regression
        guard.
    :mod:`~core.resources`
        Core resource boundary whose deferred outer-layer access pattern is
        intentionally excluded from import-time coupling.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from ...tests import SRC_AEAT, production_ast_items, production_python_files, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FORBIDDEN_CORE_PREFIXES = (
    "aeat.adapters",
    "aeat.application",
    "aeat.domain",
    "aeat.entrypoints",
)


def _absolute_import_name(module: str | None, names: list[ast.alias]) -> str:
    if module is not None:
        return module
    if not names:
        return ""
    return names[0].name


def _resolve_relative_import(path: Path, level: int, module: str | None) -> str:
    package_parts = list(path.with_suffix("").relative_to(SRC_AEAT.parent).parts)
    package_parts = package_parts[:-1]
    if level:
        package_parts = package_parts[: len(package_parts) - level + 1]
    if module:
        package_parts.extend(module.split("."))
    return ".".join(package_parts)


def _is_type_checking_guard(node: ast.stmt) -> bool:
    """Return ``True`` when ``node`` is an ``if TYPE_CHECKING:`` block."""

    if not isinstance(node, ast.If):
        return False
    test = node.test
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _iter_import_time_imports(path: Path, tree: ast.AST) -> list[str]:
    """Collect every import that executes when ``path`` is loaded.

    Imports nested inside a function or method body are deferred and do
    not run at module-load time; imports under an ``if TYPE_CHECKING:``
    guard never run at all. Both are excluded so the scan reflects the
    real import-time dependency graph the layered contract protects.
    """

    imports: list[str] = []

    def _record(node: ast.Import | ast.ImportFrom) -> None:
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
            return
        if node.level:
            imports.append(_resolve_relative_import(path, node.level, node.module))
        else:
            imports.append(_absolute_import_name(node.module, node.names))

    def _visit(body: Sequence[ast.stmt | ast.ExceptHandler]) -> None:
        for node in body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                _record(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Function/method body imports are deferred — skip them.
                continue
            elif isinstance(node, ast.ExceptHandler):
                _visit(node.body)
            elif _is_type_checking_guard(node):
                # TYPE_CHECKING-only imports never run at import time.
                continue
            elif isinstance(node, ast.If):
                _visit(node.body)
                _visit(node.orelse)
            elif isinstance(node, ast.Try):
                _visit(node.body)
                _visit(node.handlers)
                _visit(node.orelse)
                _visit(node.finalbody)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                _visit(node.body)
            elif isinstance(node, ast.ClassDef):
                # Class-body imports execute when the module loads.
                _visit(node.body)

    _visit(tree.body)
    return imports


def test_core_production_modules_do_not_import_outer_layers(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Core production modules must not import the outer layers at load time."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        relative_path = repo_relative(path)
        if not relative_path.startswith("src/aeat/core/"):
            continue
        for imported in _iter_import_time_imports(path, tree):
            if imported.startswith(_FORBIDDEN_CORE_PREFIXES):
                violations.append(f"{relative_path}:{imported}")

    assert violations == []


def test_workspace_locked_error_is_not_present_in_production_sources() -> None:
    """The removed ``WorkspaceLockedError`` symbol must not reappear."""
    removed_error_name = "Workspace" + "LockedError"
    offenders: list[str] = []
    for path in production_python_files():
        if removed_error_name in path.read_text(encoding="utf-8"):
            offenders.append(repo_relative(path))

    assert offenders == []
