"""Closed pytest parameter declarations used in import provenance proofs."""

from __future__ import annotations

import ast
from collections.abc import Iterator


def parameter_names(declared: ast.expr | None) -> tuple[str, ...]:
    """Return finite parameter names or refuse an open declaration."""
    if isinstance(declared, ast.Constant) and isinstance(declared.value, str):
        return tuple(part.strip() for part in declared.value.split(","))
    if isinstance(declared, (ast.Tuple, ast.List)) and all(_string_constant(part) for part in declared.elts):
        return tuple(
            part.value for part in declared.elts if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    raise ValueError("open parameterized argument names")


def parameter_values(
    decorator: ast.Call, cases: ast.expr | None, names: tuple[str, ...], name: str
) -> Iterator[ast.Call | ast.Constant]:
    """Admit only direct, inline finite cases for a named parameter."""
    if not isinstance(cases, (ast.Tuple, ast.List)):
        raise ValueError("open parameterized declaration cases")
    indirect = next((item.value for item in decorator.keywords if item.arg == "indirect"), None)
    if not _direct_parameter(indirect, name):
        raise ValueError("indirect parameterized declaration")
    for case in cases.elts:
        if len(names) == 1:
            value = case
        elif isinstance(case, (ast.Tuple, ast.List)) and len(case.elts) == len(names):
            value = case.elts[names.index(name)]
        else:
            raise ValueError("open parameterized declaration")
        if not isinstance(value, (ast.Call, ast.Constant)):
            raise ValueError("parameterized record must be constructed inline")
        yield value


def _direct_parameter(indirect: ast.expr | None, name: str) -> bool:
    if indirect is None or (isinstance(indirect, ast.Constant) and indirect.value is False):
        return True
    return (
        isinstance(indirect, (ast.Tuple, ast.List))
        and all(isinstance(item, ast.Constant) and isinstance(item.value, str) for item in indirect.elts)
        and name not in {item.value for item in indirect.elts if isinstance(item, ast.Constant)}
    )


def _string_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)
