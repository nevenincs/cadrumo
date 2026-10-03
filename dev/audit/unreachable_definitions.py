"""Classify Python definitions and framework or collection member reach."""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterator

from .unreachable_memo import _walked
from .unreachable_models import SymbolKind, _Definition
from .unreachable_policy import (
    _ENUM_BASE_SUFFIXES,
    _ENUM_COLLECTION_ATTRS,
    _HOOK_METHOD_NAMES,
    _HOOK_METHOD_PREFIXES,
    _PLAIN_DECORATORS,
)


def _decorator_name(node: ast.expr) -> str:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return ""


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_framework_bound(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """A method a framework reaches by convention or by decorator registration."""
    name = function.name
    if _is_dunder(name) or name in _HOOK_METHOD_NAMES or name.startswith(_HOOK_METHOD_PREFIXES):
        return True
    return any(_decorator_name(decorator) not in _PLAIN_DECORATORS for decorator in function.decorator_list)


def _is_enum_class(node: ast.ClassDef) -> bool:
    return any(_decorator_name(base).endswith(_ENUM_BASE_SUFFIXES) for base in node.bases)


def _assigned_names(node: ast.stmt) -> Iterator[str]:
    if isinstance(node, ast.Assign):
        targets: list[ast.expr] = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    else:
        return
    for target in targets:
        if isinstance(target, ast.Name):
            yield target.id
        elif isinstance(target, ast.Tuple | ast.List):
            yield from (element.id for element in target.elts if isinstance(element, ast.Name))


def _assigned_str_value(statement: ast.stmt) -> str:
    """Return the string literal a single assignment declares, else ``""``.

    Only a bare ``NAME = "literal"`` counts. A computed value, an f-string or
    a call is deliberately not followed: the point is to read the exact token
    a declaration would spell, and anything inferred would widen the data
    consult into guessing.
    """
    if isinstance(statement, ast.Assign | ast.AnnAssign):
        value = statement.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    return ""


def _class_definitions(node: ast.ClassDef) -> Iterator[_Definition]:
    member_kind = SymbolKind.ENUM_MEMBER if _is_enum_class(node) else SymbolKind.ATTRIBUTE
    for statement in node.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            if not _is_framework_bound(statement):
                yield _Definition(statement.name, f"{node.name}.{statement.name}", statement.lineno, SymbolKind.METHOD)
        elif isinstance(statement, ast.ClassDef):
            yield _Definition(statement.name, f"{node.name}.{statement.name}", statement.lineno, SymbolKind.CLASS)
            yield from (
                _Definition(inner.name, f"{node.name}.{inner.qualname}", inner.line, inner.kind, owner=inner.owner)
                for inner in _class_definitions(statement)
            )
        else:
            declared = _assigned_str_value(statement)
            for name in _assigned_names(statement):
                if not _is_dunder(name) and name != "_ignore_":
                    yield _Definition(
                        name,
                        f"{node.name}.{name}",
                        statement.lineno,
                        member_kind,
                        owner=node.name,
                        value=declared,
                    )


def _definitions(tree: ast.Module) -> Iterator[_Definition]:
    """Top-level functions, classes, constants, and the members inside each class."""
    for statement in tree.body:
        if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef):
            if not any(_decorator_name(d) not in _PLAIN_DECORATORS for d in statement.decorator_list):
                yield _Definition(statement.name, statement.name, statement.lineno, SymbolKind.FUNCTION)
        elif isinstance(statement, ast.ClassDef):
            yield _Definition(statement.name, statement.name, statement.lineno, SymbolKind.CLASS)
            yield from _class_definitions(statement)
        else:
            for name in _assigned_names(statement):
                if not _is_dunder(name):
                    yield _Definition(name, name, statement.lineno, SymbolKind.CONSTANT)


def _collection_uses(tree: ast.Module) -> set[str]:
    """Names used as a whole rather than through one attribute.

    An enum whose class is called (value lookup), iterated, passed as an
    argument, placed in a literal collection, or tested with ``in`` reaches
    every member without spelling any of them, so its members are not
    individually auditable by name.
    """
    names: set[str] = set()

    def note(node: ast.expr) -> None:
        if isinstance(node, ast.Name):
            names.add(node.id)

    for node in _walked(tree):
        if not _note_collection_expressions(node, note):
            _note_collection_membership(node, note)
    return names


def _note_collection_expressions(node: ast.AST, note: Callable[[ast.expr], None]) -> bool:
    """Read calls, iterables and literal sequences through their original cases."""
    if isinstance(node, ast.Call):
        note(node.func)
        for arg in node.args:
            note(arg)
        for keyword in node.keywords:
            note(keyword.value)
        return True
    elif isinstance(node, ast.For | ast.AsyncFor | ast.comprehension):
        note(node.iter)
        return True
    elif isinstance(node, ast.Tuple | ast.List | ast.Set):
        for element in node.elts:
            note(element)
        return True
    return False


def _note_collection_membership(node: ast.AST, note: Callable[[ast.expr], None]) -> None:
    """Read mapping values, membership comparators and explicit enum collections."""
    if isinstance(node, ast.Dict):
        for value in node.values:
            note(value)
    elif isinstance(node, ast.Compare):
        for operator, comparator in zip(node.ops, node.comparators, strict=True):
            if isinstance(operator, ast.In | ast.NotIn):
                note(comparator)
    elif isinstance(node, ast.Attribute) and node.attr in _ENUM_COLLECTION_ATTRS:
        note(node.value)
