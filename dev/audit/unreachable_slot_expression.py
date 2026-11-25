"""Recognize finite schema slot reads within a method."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping


def slot_expression(
    expression: ast.expr | None,
    aliases: Mapping[str, str],
    name: str,
    arguments: ast.arguments,
    shadowed_getattr: bool,
    qualify: Callable[[str, ast.expr], str],
) -> str:
    """Resolve a slot name from a closed getter expression."""
    if isinstance(expression, ast.Name):
        return aliases.get(expression.id, "")
    if isinstance(expression, ast.Attribute):
        return _self_slot(expression)
    if isinstance(expression, ast.Call):
        if qualify(name, expression.func) == "typing.cast" and len(expression.args) == 2:
            return slot_expression(expression.args[1], aliases, name, arguments, shadowed_getattr, qualify)
        if _slot_getattr(expression, arguments, shadowed_getattr):
            value = expression.args[1]
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    return ""


def _slot_getattr(expression: ast.Call, arguments: ast.arguments, shadowed_getattr: bool) -> bool:
    return (
        isinstance(expression.func, ast.Name)
        and expression.func.id == "getattr"
        and len(expression.args) >= 2
        and isinstance(expression.args[0], ast.Name)
        and expression.args[0].id in {"self", "cls"}
        and isinstance(expression.args[1], ast.Constant)
        and isinstance(expression.args[1].value, str)
        and not shadowed_getattr
        and not any(argument.arg == "getattr" for argument in arguments.args)
    )


def _self_slot(expression: ast.Attribute) -> str:
    return expression.attr if isinstance(expression.value, ast.Name) and expression.value.id in {"self", "cls"} else ""
