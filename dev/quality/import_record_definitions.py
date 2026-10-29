"""Index lexical class, function, and alias definitions."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .import_check_models import SourceModule
from .import_record_models import SourceExpression


def index_definitions(modules: Mapping[str, SourceModule]) -> tuple[dict[str, ast.AST], dict[str, ast.ClassDef]]:
    """Collect canonical declaration owners and class methods."""
    definitions: dict[str, ast.AST] = {}
    classes: dict[str, ast.ClassDef] = {}
    for module in modules.values():
        for node in module.tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions[f"{module.name}.{node.name}"] = node
            if isinstance(node, ast.TypeAlias):
                definitions[f"{module.name}.{node.name.id}"] = node
            if isinstance(node, ast.ClassDef):
                classes[f"{module.name}.{node.name}"] = node
                _index_methods(module.name, node, definitions)
    return definitions, classes


def _index_methods(module: str, node: ast.ClassDef, definitions: dict[str, ast.AST]) -> None:
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            definitions[f"{module}.{node.name}.{child.name}"] = child


def default_argument(reference: str, name: str, fields: tuple[ast.AnnAssign, ...]) -> SourceExpression | None:
    """Resolve the declared default for a constructor field."""
    for item in fields:
        if isinstance(item.target, ast.Name) and item.target.id == name and item.value is not None:
            return SourceExpression(reference.rpartition(".")[0], item.value)
    return None


def field_names(fields: tuple[ast.AnnAssign, ...]) -> list[str]:
    """Return named constructor fields in declaration order."""
    return [item.target.id for item in fields if isinstance(item.target, ast.Name)]
