"""Shared alias-assignment scan for the broad-exception ratchets."""

from __future__ import annotations

import ast

from cadrumo.tests.inventory import qualified_name


def broad_alias_assignments_from_target(
    target: ast.expr,
    value: ast.expr,
) -> list[tuple[str, tuple[str, ...]]]:
    """Return broad-exception alias assignments from one target/value pair."""
    if isinstance(target, ast.Name):
        if isinstance(value, ast.Tuple | ast.List | ast.Set):
            return [(qualified_name(element), (target.id,)) for element in value.elts]
        return [(qualified_name(value), (target.id,))]
    if isinstance(target, ast.Tuple | ast.List) and isinstance(value, ast.Tuple | ast.List):
        assignments: list[tuple[str, tuple[str, ...]]] = []
        for target_element, value_element in zip(target.elts, value.elts, strict=False):
            if isinstance(target_element, ast.Name):
                assignments.append((qualified_name(value_element), (target_element.id,)))
        return assignments
    return []
