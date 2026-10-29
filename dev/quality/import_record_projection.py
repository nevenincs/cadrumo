"""Resolve bounded iteration projections and import visibility."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .import_check_models import SourceModule
from .import_record_models import SourceExpression


def iteration_projection(source: SourceExpression, projection: tuple[int, ...]) -> SourceExpression:
    """Resolve a supported iteration projection."""
    node = source.node
    if len(projection) != 1 or not isinstance(node, ast.Call):
        raise ValueError("unsupported iteration projection")
    index = projection[0]
    return SourceExpression(source.module, _projected_value(node, index), source.bindings)


def _projected_value(node: ast.Call, index: int) -> ast.expr:
    if _named(node.func, "zip") and len(node.args) > index:
        return node.args[index]
    if _named(node.func, "enumerate") and node.args and index == 1:
        return node.args[0]
    if isinstance(node.func, ast.Attribute) and node.func.attr == "items" and index == 1:
        return node.func.value
    raise ValueError("unknown iteration projection")


def reference_visible(modules: Mapping[str, SourceModule], module: str, reference: str) -> bool:
    """Identify whether a module can reference the canonical definition."""
    if reference.rpartition(".")[0] == module:
        return True
    for binding in modules[module].bindings.values():
        if binding.target is None:
            continue
        prefix = binding.target
        if binding.imported_name is not None:
            prefix = f"{prefix}.{binding.imported_name}"
        if reference == prefix or reference.startswith(f"{prefix}."):
            return True
    return False


def _named(node: ast.expr, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name
