"""Import evaluation strings."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, cast

from .import_target_value_sets import bounded, combine, products, union

if TYPE_CHECKING:
    from .import_target_evaluation import TargetAssignment, TargetEvaluationContext


def evaluate_name(
    self: TargetEvaluationContext, node: ast.Name, lineno: int, resolving: set[tuple[int, str]], scope: ast.AST | None
) -> frozenset[str] | None:
    """Evaluate name."""
    if node.id == "__name__" and self.module_name is not None:
        return frozenset({self.module_name})
    key = (id(scope) if scope is not None else 0, node.id)
    if key in resolving:
        return None
    assignments = self.latest_values(node.id, lineno, scope)
    if assignments is None:
        return None
    resolving.add(key)
    result: set[str] = set()
    for assignment in assignments:
        evaluated = _evaluate_assignment(self, assignment, resolving, scope)
        if evaluated is None:
            resolving.remove(key)
            return None
        result.update(evaluated)
    resolving.remove(key)
    return bounded(result)


def evaluate_joined_string(
    self: TargetEvaluationContext,
    node: ast.JoinedStr,
    lineno: int,
    resolving: set[tuple[int, str]],
    scope: ast.AST | None,
) -> frozenset[str] | None:
    """Evaluate joined string."""
    values: frozenset[str] | None = frozenset({""})
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            pieces = frozenset({part.value})
        elif isinstance(part, ast.FormattedValue) and part.format_spec is None and part.conversion == -1:
            pieces = self.evaluate_values(part.value, lineno, resolving, scope)
        else:
            return None
        values = combine(values, pieces)
        if values is None:
            return None
    return values


def _evaluate_collection(
    self: TargetEvaluationContext,
    node: ast.Tuple | ast.List | ast.Set,
    lineno: int,
    resolving: set[tuple[int, str]],
    scope: ast.AST | None,
) -> frozenset[str] | None:
    """Evaluate collection."""
    result: set[str] = set()
    for element in node.elts:
        evaluated = self.evaluate_values(element, lineno, resolving, scope)
        if evaluated is None:
            return None
        result.update(evaluated)
    return bounded(result)


def _evaluate_subscript(
    self: TargetEvaluationContext,
    node: ast.Subscript,
    lineno: int,
    resolving: set[tuple[int, str]],
    scope: ast.AST | None,
) -> frozenset[str] | None:
    """Evaluate subscript."""
    values = self.sequence_values(node.value, lineno, resolving, scope)
    if values is None:
        return None
    if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
        try:
            return frozenset({values[node.slice.value]})
        except IndexError:
            return None
    return frozenset(values)


def _evaluate_format_call(
    self: TargetEvaluationContext, node: ast.Call, lineno: int, resolving: set[tuple[int, str]], scope: ast.AST | None
) -> frozenset[str] | None:
    """Evaluate format call."""
    bases = self.evaluate_values(cast("ast.Attribute", node.func).value, lineno, resolving, scope)
    if bases is None:
        return None
    positional: list[frozenset[str]] = []
    for argument in node.args:
        values = self.evaluate_values(argument, lineno, resolving, scope)
        if values is None:
            return None
        positional.append(values)
    keyword_names: list[str] = []
    keyword_values: list[frozenset[str]] = []
    for keyword in node.keywords:
        if keyword.arg is None:
            return None
        values = self.evaluate_values(keyword.value, lineno, resolving, scope)
        if values is None:
            return None
        keyword_names.append(keyword.arg)
        keyword_values.append(values)
    return _evaluate_formatted_products(bases, positional, keyword_names, keyword_values)


def evaluate_compound(
    self: TargetEvaluationContext, node: ast.AST, lineno: int, resolving: set[tuple[int, str]], scope: ast.AST | None
) -> frozenset[str] | None:
    """Evaluate compound."""
    if isinstance(node, ast.IfExp):
        return union(
            self.evaluate_values(node.body, lineno, resolving, scope),
            self.evaluate_values(node.orelse, lineno, resolving, scope),
        )
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return _evaluate_collection(self, node, lineno, resolving, scope)
    if isinstance(node, ast.Subscript):
        return _evaluate_subscript(self, node, lineno, resolving, scope)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        return _evaluate_format_call(self, node, lineno, resolving, scope)
    return None


def _evaluate_assignment(
    self: TargetEvaluationContext, assignment: TargetAssignment, resolving: set[tuple[int, str]], scope: ast.AST | None
) -> frozenset[str] | None:
    """Evaluate assignment."""
    if assignment.unpack:
        evaluated = self.unpacked_values(
            assignment.value,
            assignment.projection,
            assignment.lineno - 1,
            resolving,
            scope,
        )
    elif assignment.projection:
        evaluated = self.values_at_indices(
            assignment.value,
            assignment.projection,
            assignment.lineno - 1,
            resolving,
            scope,
        )
    else:
        evaluated = self.evaluate_values(assignment.value, assignment.lineno - 1, resolving, scope)
    return evaluated


def _evaluate_formatted_products(
    bases: frozenset[str],
    positional: list[frozenset[str]],
    keyword_names: list[str],
    keyword_values: list[frozenset[str]],
) -> frozenset[str] | None:
    """Evaluate formatted products."""
    result: set[str] = set()
    for base in bases:
        for values in products(positional):
            for named in products(keyword_values):
                try:
                    result.add(base.format(*values, **dict(zip(keyword_names, named, strict=True))))
                except (IndexError, KeyError, ValueError):
                    return None
    return bounded(result)
