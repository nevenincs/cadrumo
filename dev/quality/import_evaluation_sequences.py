"""Import evaluation sequences."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .import_target_evaluation import TargetEvaluationContext


def sequence_literal_nodes(
    self: TargetEvaluationContext,
    node: ast.Tuple | ast.List,
    lineno: int,
    resolving: set[tuple[int, str]],
    scope: ast.AST | None,
) -> tuple[ast.AST, ...] | None:
    """Sequence literal nodes."""
    elements: list[ast.AST] = []
    for element in node.elts:
        if isinstance(element, ast.Starred):
            expanded = self.sequence_nodes(element.value, lineno, resolving, scope)
            if expanded is None:
                return None
            elements.extend(expanded)
        else:
            elements.append(element)
    return tuple(elements)


def sequence_dict_nodes(
    self: TargetEvaluationContext, node: ast.Dict, lineno: int, resolving: set[tuple[int, str]], scope: ast.AST | None
) -> tuple[ast.AST, ...] | None:
    """Sequence dict nodes."""
    elements: list[ast.AST] = []
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None:
            return None
        elements.append(ast.Tuple(elts=[key, value], ctx=ast.Load()))
    return tuple(elements)


def sequence_name_nodes(
    self: TargetEvaluationContext, node: ast.Name, lineno: int, resolving: set[tuple[int, str]], scope: ast.AST | None
) -> tuple[ast.AST, ...] | None:
    """Sequence name nodes."""
    key = (id(scope) if scope is not None else 0, node.id)
    if key in resolving:
        return None
    assignments = self.latest_values(node.id, lineno, scope)
    if not assignments:
        return None
    resolving.add(key)
    sequences: list[ast.AST] = []
    for assignment in assignments:
        if assignment.projection:
            resolving.remove(key)
            return None
        values = self.sequence_nodes(assignment.value, assignment.lineno - 1, resolving, scope)
        if values is None:
            resolving.remove(key)
            return None
        sequences.extend(values)
    resolving.remove(key)
    return tuple(sequences)
