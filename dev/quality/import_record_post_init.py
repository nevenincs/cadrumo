"""Proof of permitted dataclass post-init operations for import declarations."""

from __future__ import annotations

import ast
from collections.abc import Callable

from .import_module_syntax import qualified_name


def post_init_is_closed(module: str, definition: ast.ClassDef, reference: Callable[[str, ast.AST], str | None]) -> bool:
    """Refuse post-init code whose effects or receiver uses cannot be proved closed."""
    fields = {
        item.target.id
        for item in definition.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }
    for method in definition.body:
        if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name != "__post_init__":
            continue
        if any(not _closed_node(module, node, fields, reference) for node in ast.walk(method)):
            return False
    return True


def _closed_node(module: str, node: ast.AST, fields: set[str], reference: Callable[[str, ast.AST], str | None]) -> bool:
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr not in fields
    ):
        return False
    if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
        return False
    if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
        return False
    return not isinstance(node, ast.Call) or _closed_call(module, node, reference)


def _closed_call(module: str, node: ast.Call, reference: Callable[[str, ast.AST], str | None]) -> bool:
    if any(
        isinstance(child, ast.Name) and child.id == "self" for child in ast.walk(node.func)
    ) and not _safe_startswith(node):
        return False
    arguments = (*node.args, *(keyword.value for keyword in node.keywords))
    if not any(_passes_raw_self(argument) for argument in arguments):
        return True
    return _closed_assignment(module, node, reference)


def _safe_startswith(node: ast.Call) -> bool:
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "startswith"
        and qualified_name(node.func.value) == "self.module"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and not node.keywords
    )


def _closed_assignment(module: str, node: ast.Call, reference: Callable[[str, ast.AST], str | None]) -> bool:
    if qualified_name(node.func) != "object.__setattr__" or len(node.args) != 3 or node.keywords:
        return False
    field, value = node.args[1:]
    if not isinstance(field, ast.Constant) or field.value not in {"module", "package"}:
        return False
    if field.value == "package" and isinstance(value, ast.Constant) and value.value is None:
        return True
    return _resolved_name(module, value, reference)


def _passes_raw_self(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return False
    return (isinstance(node, ast.Name) and node.id == "self") or any(
        _passes_raw_self(child) for child in ast.iter_child_nodes(node)
    )


def normalizes_module(module: str, definition: ast.ClassDef, reference: Callable[[str, ast.AST], str | None]) -> bool:
    """Identify the permitted standard module-name normalization."""
    return any(
        _normalization_call(module, node, reference)
        for method in definition.body
        if isinstance(method, ast.FunctionDef) and method.name == "__post_init__"
        for node in ast.walk(method)
    )


def _normalization_call(module: str, node: ast.AST, reference: Callable[[str, ast.AST], str | None]) -> bool:
    if not isinstance(node, ast.Call) or qualified_name(node.func) != "object.__setattr__" or len(node.args) != 3:
        return False
    field, value = node.args[1:]
    if not isinstance(field, ast.Constant) or field.value != "module" or not isinstance(value, ast.Call):
        return False
    return reference(module, value.func) == "importlib.util.resolve_name" and [
        qualified_name(arg) for arg in value.args
    ] == ["self.module", "self.package"]


def _resolved_name(module: str, value: ast.expr, reference: Callable[[str, ast.AST], str | None]) -> bool:
    if not isinstance(value, ast.Call) or reference(module, value.func) != "importlib.util.resolve_name":
        return False
    return [qualified_name(argument) for argument in value.args] == [
        "self.module",
        "self.package",
    ] and not value.keywords


def is_dataclass(reference: str, definition: ast.ClassDef, resolve: Callable[[str, ast.AST], str | None]) -> bool:
    """Prove a class uses the supported dataclass construction semantics."""
    module = reference.rpartition(".")[0]
    if _custom_construction(definition):
        return False
    if len(definition.decorator_list) != 1:
        return False
    decorator = definition.decorator_list[0]
    if resolve(module, decorator.func if isinstance(decorator, ast.Call) else decorator) != "dataclasses.dataclass":
        return False
    if isinstance(decorator, ast.Call) and any(
        keyword.arg == "init" and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is True)
        for keyword in decorator.keywords
    ):
        return False
    return post_init_is_closed(module, definition, resolve)


def _custom_construction(definition: ast.ClassDef) -> bool:
    return bool(definition.bases or definition.keywords) or any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"__init__", "__new__", "__getattribute__", "__getattr__", "__setattr__"}
        for node in definition.body
    )
