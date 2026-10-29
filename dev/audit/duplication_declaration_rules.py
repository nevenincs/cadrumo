"""Resolve inert declarations and stable imported names."""

from __future__ import annotations

import ast
from collections.abc import Sequence


def declaration_imported_names(tree: ast.Module, module: str, name: str) -> set[str]:
    """Resolve an imported name only when it has not been rebound."""
    aliases = {
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == module and not node.level
        for alias in node.names
        if alias.name == name
    }
    rebound = _declaration_rebindings(tree, module, name)
    return aliases - rebound


def _declaration_rebindings(tree: ast.Module, module: str, name: str) -> set[str]:
    rebound = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
    rebound.update(
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    )
    rebound.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    rebound.update(_other_import_names(tree, module, name))
    return rebound


def _other_import_names(tree: ast.Module, module: str, name: str) -> set[str]:
    return set(
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
        if not (isinstance(node, ast.ImportFrom) and node.module == module and alias.name == name and not node.level)
    )


def inert_declaration(value: ast.AST | None) -> bool:
    """Return whether an expression is inert under the supported grammar."""
    if value is None or isinstance(value, ast.Constant | ast.Name):
        return True
    if isinstance(value, ast.Tuple | ast.List | ast.Set):
        return all(inert_declaration(item) for item in value.elts)
    if isinstance(value, ast.Dict):
        return _inert_dictionary(value)
    return (
        isinstance(value, ast.UnaryOp)
        and isinstance(value.op, ast.UAdd | ast.USub)
        and isinstance(value.operand, ast.Constant)
    )


def _inert_dictionary(value: ast.Dict) -> bool:
    return all(
        key is not None and inert_declaration(key) and inert_declaration(item)
        for key, item in zip(value.keys, value.values, strict=True)
    )


def declaration_docstring(node: ast.stmt) -> bool:
    """Identify a literal docstring statement."""
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def declaration_has_call(nodes: Sequence[ast.AST]) -> bool:
    """Return whether any expression contains a call."""
    return any(isinstance(part, ast.Call) for node in nodes for part in ast.walk(node))
