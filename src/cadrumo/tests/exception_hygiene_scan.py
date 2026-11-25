"""AST scans that find exception handling a production module must not contain."""

from __future__ import annotations

import ast

_LOGGING_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical"})


def swallowed_with_pass(tree: ast.AST) -> list[ast.ExceptHandler]:
    """Return handlers whose whole body is ``pass``."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
    ]


def contextlib_suppress_uses(tree: ast.AST) -> list[ast.With]:
    """Return ``with`` statements that enter ``suppress(...)`` or ``contextlib.suppress(...)``."""
    offenders: list[ast.With] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        for item in node.items:
            context_expr = item.context_expr
            if isinstance(context_expr, ast.Call):
                context_expr = context_expr.func
            if (isinstance(context_expr, ast.Attribute) and context_expr.attr == "suppress") or (
                isinstance(context_expr, ast.Name) and context_expr.id == "suppress"
            ):
                offenders.append(node)
    return offenders


def bare_excepts(tree: ast.AST) -> list[ast.ExceptHandler]:
    """Return handlers that name no exception class."""
    return [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler) and node.type is None]


def broad_handlers_without_raise_or_log(tree: ast.AST) -> list[ast.ExceptHandler]:
    """Return ``Exception``/``BaseException`` handlers that neither re-raise nor log."""
    offenders: list[ast.ExceptHandler] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.type is None or not _is_broad_exception_type(node.type):
            continue
        has_raise = any(isinstance(child, ast.Raise) for child in ast.walk(node))
        has_log = any(_is_logging_call(child) for child in ast.walk(node))
        if not has_raise and not has_log:
            offenders.append(node)
    return offenders


def _is_broad_exception_type(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"Exception", "BaseException"}
    if isinstance(node, ast.Tuple):
        return any(_is_broad_exception_type(item) for item in node.elts)
    return False


def _is_logging_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in _LOGGING_METHODS
