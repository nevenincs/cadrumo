"""Read explicit receiver types from defining modules for qualified consumer checks."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass, field

from .unreachable_frameworks import expression_name, import_bindings
from .unreachable_models import ShippedModule


@dataclass(frozen=True)
class ReceiverTypes:
    """Constructed module values and explicitly declared callable return types."""

    values: Mapping[str, str]
    returns: Mapping[str, str]
    classes: frozenset[str]
    fields: Mapping[str, str]
    contexts: Mapping[str, str]
    iterables: Mapping[str, str]


def _qualify(node: ast.expr, name: str, bindings: Mapping[str, str]) -> str:
    spelling = expression_name(node)
    head, separator, tail = spelling.partition(".")
    return f"{bindings.get(head, f'{name}.{head}')}{separator}{tail}"


def iterable_receiver_type(
    annotation: ast.expr, name: str, bindings: Mapping[str, str], classes: frozenset[str]
) -> str:
    """Resolve a homogeneous declared iterable, keeping unknown and mixed elements unknown."""
    if not isinstance(annotation, ast.Subscript):
        return ""
    spelling = expression_name(annotation.value)
    qualified = _qualify(annotation.value, name, bindings)
    if spelling.partition(".")[0] in bindings:
        if qualified not in {
            "builtins.tuple",
            "builtins.list",
            "builtins.set",
            "builtins.frozenset",
            "collections.abc.Iterable",
            "collections.abc.Iterator",
            "collections.abc.Sequence",
            "typing.Iterable",
            "typing.Iterator",
            "typing.Sequence",
        }:
            return ""
    elif spelling not in {"tuple", "list", "set", "frozenset"}:
        return ""
    return _iterable_item(annotation, name, bindings, classes)


def _iterable_item(annotation: ast.Subscript, name: str, bindings: Mapping[str, str], classes: frozenset[str]) -> str:
    arguments = list(annotation.slice.elts) if isinstance(annotation.slice, ast.Tuple) else [annotation.slice]
    types = {
        _qualify(item, name, bindings)
        for item in arguments
        if not isinstance(item, ast.Constant) or item.value is not Ellipsis
    }
    return next(iter(types)) if len(types) == 1 and types <= classes else ""


def receiver_types(
    modules: Mapping[str, ShippedModule], *, known_classes: frozenset[str] = frozenset()
) -> ReceiverTypes:
    """Resolve declared factories and constants without importing their modules."""
    classes = known_classes | frozenset(
        f"{name}.{node.name}"
        for name, module in modules.items()
        for node in module.tree.body
        if isinstance(node, ast.ClassDef)
    )
    index = _ReceiverIndex(classes)
    for name, module in modules.items():
        bindings = import_bindings(module)
        for owner in module.tree.body:
            _index_owner(name, owner, bindings, index)
    return ReceiverTypes(index.values, index.returns, classes, index.fields, index.contexts, index.iterables)


@dataclass
class _ReceiverIndex:
    classes: frozenset[str]
    values: dict[str, str] = field(default_factory=dict)
    returns: dict[str, str] = field(default_factory=dict)
    fields: dict[str, str] = field(default_factory=dict)
    contexts: dict[str, str] = field(default_factory=dict)
    iterables: dict[str, str] = field(default_factory=dict)


def _index_owner(name: str, owner: ast.stmt, bindings: Mapping[str, str], index: _ReceiverIndex) -> None:
    if isinstance(owner, ast.ClassDef):
        _class_fields(name, owner, bindings, index)
    functions = owner.body if isinstance(owner, ast.ClassDef) else [owner]
    for function in functions:
        if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef) and function.returns is not None:
            _function_return(name, owner, function, bindings, index)
    if isinstance(owner, ast.Assign | ast.AnnAssign) and isinstance(owner.value, ast.Call):
        _constant_receiver(name, owner, bindings, index)


def _constant_receiver(
    name: str, owner: ast.Assign | ast.AnnAssign, bindings: Mapping[str, str], index: _ReceiverIndex
) -> None:
    if not isinstance(owner.value, ast.Call):
        return
    result = _qualify(owner.value.func, name, bindings)
    targets = owner.targets if isinstance(owner, ast.Assign) else [owner.target]
    if result in index.classes:
        index.values.update((f"{name}.{target.id}", result) for target in targets if isinstance(target, ast.Name))


def _class_fields(name: str, owner: ast.ClassDef, bindings: Mapping[str, str], index: _ReceiverIndex) -> None:
    for member in owner.body:
        if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
            target = _qualify(member.annotation, name, bindings)
            if target in index.classes:
                index.fields[f"{name}.{owner.name}.{member.target.id}"] = target
            item_type = iterable_receiver_type(member.annotation, name, bindings, index.classes)
            if item_type:
                index.iterables[f"{name}.{owner.name}.{member.target.id}"] = item_type


def _function_return(
    name: str,
    owner: ast.stmt,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    bindings: Mapping[str, str],
    index: _ReceiverIndex,
) -> None:
    annotation = function.returns
    if annotation is None:
        return
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        annotation = ast.parse(annotation.value, mode="eval").body
    result = _qualify(annotation, name, bindings)
    prefix = f"{name}.{owner.name}." if isinstance(owner, ast.ClassDef) else f"{name}."
    item_type = iterable_receiver_type(annotation, name, bindings, index.classes)
    if item_type:
        index.iterables[prefix + function.name] = item_type
    if isinstance(owner, ast.ClassDef) and expression_name(annotation) == "Self":
        result = f"{name}.{owner.name}"
    if result in index.classes:
        index.returns[prefix + function.name] = result
        if _property_function(function):
            index.fields[prefix + function.name] = result
    _context_receiver(name, prefix, function, annotation, bindings, index)


def _context_receiver(
    name: str,
    prefix: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    annotation: ast.expr,
    bindings: Mapping[str, str],
    index: _ReceiverIndex,
) -> None:
    if isinstance(annotation, ast.Subscript) and any(
        _qualify(decorator, name, bindings) in {"contextlib.contextmanager", "contextlib.asynccontextmanager"}
        for decorator in function.decorator_list
    ):
        yielded = _qualify(annotation.slice, name, bindings)
        if yielded in index.classes:
            index.contexts[prefix + function.name] = yielded


def _property_function(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(expression_name(decorator) == "property" for decorator in function.decorator_list)
