"""AST helpers shared by the terminal-precondition source censuses."""

from __future__ import annotations

import ast


def call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def keyword_value(call: ast.Call, name: str) -> ast.expr:
    value = next((keyword.value for keyword in call.keywords if keyword.arg == name), None)
    assert value is not None, f"missing {name}"
    return value


def fact_expressions(
    call: ast.Call,
    assignments: dict[str, ast.expr] | None = None,
) -> tuple[tuple[str, str], ...]:
    facts = keyword_value(call, "facts")
    if isinstance(facts, ast.Name) and assignments is not None:
        facts = assignments[facts.id]
    assert isinstance(facts, ast.Dict)
    values: list[tuple[str, str]] = []
    for key, value in zip(facts.keys, facts.values, strict=True):
        assert isinstance(key, ast.Constant) and isinstance(key.value, str)
        values.append((key.value, ast.unparse(value)))
    return tuple(values)
