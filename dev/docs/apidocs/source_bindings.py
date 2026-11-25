"""Resolve top-level names rebound by source statements."""

from __future__ import annotations

import ast


def statement_binds_name(statement: ast.stmt, symbol: str) -> bool:
    """Return whether a module-level statement binds *symbol*."""
    if isinstance(statement, (ast.AugAssign, ast.Delete)):
        return False
    if isinstance(statement, ast.ImportFrom):
        return any((alias.asname or alias.name) == symbol for alias in statement.names)
    return symbol in bound_names(statement)


def _target_names(target: ast.expr) -> set[str]:
    """Return the names assigned by one target."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return {name for item in target.elts for name in _target_names(item)}
    return set()


def bound_names(statement: ast.stmt) -> set[str]:
    """Return the names bound by one top-level statement."""
    if isinstance(statement, ast.TypeAlias):
        return {statement.name.id}
    if isinstance(statement, ast.Assign | ast.AugAssign | ast.Delete):
        targets = statement.targets if isinstance(statement, ast.Assign | ast.Delete) else (statement.target,)
        return {name for target in targets for name in _target_names(target)}
    if isinstance(statement, ast.AnnAssign) and statement.value is not None:
        return _target_names(statement.target)
    return _other_bound_names(statement)


def _other_bound_names(statement: ast.stmt) -> set[str]:
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        return _import_names(statement)
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {statement.name}
    if isinstance(statement, (ast.For, ast.AsyncFor)):
        return _target_names(statement.target)
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return {
            target
            for item in statement.items
            if item.optional_vars is not None
            for target in _target_names(item.optional_vars)
        }
    return set()


def _import_names(statement: ast.Import | ast.ImportFrom) -> set[str]:
    if isinstance(statement, ast.Import):
        return {alias.asname or alias.name.split(".", maxsplit=1)[0] for alias in statement.names}
    return {alias.asname or alias.name for alias in statement.names if alias.name != "*"}
