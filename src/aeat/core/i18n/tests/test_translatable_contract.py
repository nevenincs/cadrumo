"""Repository-wide guard for the ``Translatable`` declaration contract."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import override

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SOURCE_ROOT = Path("src/aeat")
_TRANSLATABLE_EXPORT = Path("src/aeat/core/i18n/__init__.py")
_TRANSLATION_RENDERER = Path("src/aeat/core/i18n/_render.py")


def _location(path: Path, node: ast.AST, message: str) -> str:
    lineno = getattr(node, "lineno", 1)
    return f"{path.as_posix()}:{lineno}: {message}"


def _iter_python_sources() -> list[Path]:
    return sorted(_SOURCE_ROOT.rglob("*.py"))


def _target_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    if isinstance(target, ast.Tuple | ast.List):
        names: list[str] = []
        for element in target.elts:
            names.extend(_target_names(element))
        return names
    return []


def _is_i18n_tr_import(module: str | None, alias: ast.alias) -> bool:
    if alias.name != "tr":
        return False
    if alias.asname is not None:
        return False
    return module is not None and (module == "_render" or module == "i18n" or module.endswith(".i18n"))


class _TranslatableContractVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.violations: list[str] = []

    @override
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.asname == "tr":
                self.violations.append(_location(self.path, node, "imports a non-i18n symbol as reserved name 'tr'"))
        self.generic_visit(node)

    @override
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            bound_name = alias.asname or alias.name
            if alias.name == "Translatable":
                if self.path == _TRANSLATABLE_EXPORT and alias.asname is None:
                    continue
                if alias.asname != "tr":
                    self.violations.append(
                        _location(self.path, node, "imports Translatable without the required 'as tr' alias")
                    )
                continue
            if bound_name == "tr" and not _is_i18n_tr_import(node.module, alias):
                self.violations.append(_location(self.path, node, "binds reserved name 'tr' from a non-i18n import"))
        self.generic_visit(node)

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_named_binding(node.name, node)
        self._check_arguments(node.args, node)
        self.generic_visit(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_named_binding(node.name, node)
        self._check_arguments(node.args, node)
        self.generic_visit(node)

    @override
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._check_named_binding(node.name, node)
        self.generic_visit(node)

    @override
    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._check_targets(target, node)
        self.generic_visit(node)

    @override
    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._check_targets(node.target, node)
        self.generic_visit(node)

    @override
    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._check_targets(node.target, node)
        self.generic_visit(node)

    @override
    def visit_For(self, node: ast.For) -> None:
        self._check_targets(node.target, node)
        self.generic_visit(node)

    @override
    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self._check_targets(node.target, node)
        self.generic_visit(node)

    @override
    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._check_targets(item.optional_vars, node)
        self.generic_visit(node)

    @override
    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        for item in node.items:
            if item.optional_vars is not None:
                self._check_targets(item.optional_vars, node)
        self.generic_visit(node)

    @override
    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self._check_named_binding(node.name, node)
        self.generic_visit(node)

    @override
    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._check_targets(node.target, node)
        self.generic_visit(node)

    @override
    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id == "Translatable":
                self.violations.append(_location(self.path, node, "constructs Translatable directly; use tr(...)"))
            elif node.func.id == "_t":
                self.violations.append(_location(self.path, node, "calls forbidden translation helper '_t'"))
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "Translatable":
            self.violations.append(
                _location(self.path, node, "constructs Translatable through an attribute; use tr(...)")
            )
        self.generic_visit(node)

    def _check_arguments(self, arguments: ast.arguments, node: ast.AST) -> None:
        params = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
        if arguments.vararg is not None:
            params.append(arguments.vararg)
        if arguments.kwarg is not None:
            params.append(arguments.kwarg)
        for param in params:
            self._check_named_binding(param.arg, node)

    def _check_targets(self, target: ast.AST, node: ast.AST) -> None:
        for name in _target_names(target):
            self._check_named_binding(name, node)

    def _check_named_binding(self, name: str, node: ast.AST) -> None:
        if name == "_t":
            self.violations.append(_location(self.path, node, "binds forbidden translation helper name '_t'"))
        elif name == "tr" and not (self.path == _TRANSLATION_RENDERER and isinstance(node, ast.FunctionDef)):
            self.violations.append(_location(self.path, node, "shadows reserved i18n name 'tr'"))


def test_translatable_instances_use_only_tr_alias_without_shadowing() -> None:
    """``Translatable`` values must be declared as ``tr(...)`` with no local shadowing."""

    violations: list[str] = []
    for path in _iter_python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        visitor = _TranslatableContractVisitor(path)
        visitor.visit(tree)
        violations.extend(visitor.violations)

    assert violations == []
