"""Recognize actual whole-record dataclass reads, including field-walking serializers."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from .unreachable_frameworks import expression_name, import_bindings
from .unreachable_members import resolved_calls
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import receiver_types


def dataclass_member_uses(
    modules: Mapping[str, ShippedModule], reachable: frozenset[str]
) -> frozenset[tuple[str, str]]:
    """A constructor alone cannot prove that a dataclass's fields are consumed."""
    bindings = {name: import_bindings(module) for name, module in modules.items()}

    def qualify(name: str, node: ast.expr) -> str:
        spelling = expression_name(node)
        head, separator, tail = spelling.partition(".")
        return f"{bindings[name].get(head, f'{name}.{head}')}{separator}{tail}"

    classes = _dataclass_classes(modules, qualify)
    serializers = _serializers(modules, reachable, qualify, bindings)
    receivers = receiver_types(modules)
    pending = [
        argument
        for name in reachable
        for call in resolved_calls(modules[name], frozenset(modules), receivers)
        if call.target in serializers
        for argument in call.arguments
        if argument in classes
    ]
    return _dataclass_fields(pending, classes, qualify)


def _dataclass_classes(
    modules: Mapping[str, ShippedModule], qualify: Callable[[str, ast.expr], str]
) -> dict[str, tuple[str, ast.ClassDef]]:
    classes = {
        f"{name}.{node.name}": (name, node)
        for name, module in modules.items()
        for node in module.tree.body
        if isinstance(node, ast.ClassDef)
        and any(
            qualify(name, decorator.func if isinstance(decorator, ast.Call) else decorator) == "dataclasses.dataclass"
            for decorator in node.decorator_list
        )
    }
    return classes


def _serializers(
    modules: Mapping[str, ShippedModule],
    reachable: frozenset[str],
    qualify: Callable[[str, ast.expr], str],
    bindings: Mapping[str, Mapping[str, str]],
) -> set[str]:
    serializers: set[str] = {"dataclasses.asdict", "dataclasses.astuple"}
    for name in reachable:
        for function in modules[name].tree.body:
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef) or not function.args.args:
                continue
            _index_serializer(name, function, qualify, bindings, serializers)
    return serializers


def _dataclass_fields(
    pending: list[str], classes: Mapping[str, tuple[str, ast.ClassDef]], qualify: Callable[[str, ast.expr], str]
) -> frozenset[tuple[str, str]]:
    visited: set[str] = set()
    used: set[tuple[str, str]] = set()
    while pending:
        target = pending.pop()
        if target in visited:
            continue
        visited.add(target)
        name, node = classes[target]
        for member in node.body:
            if not isinstance(member, ast.AnnAssign) or not isinstance(member.target, ast.Name):
                continue
            if qualify(name, member.annotation) in {"typing.ClassVar", "dataclasses.InitVar", "dataclasses.KW_ONLY"}:
                continue
            used.add((name, f"{node.name}.{member.target.id}"))
            pending.extend(_nested_classes(member.annotation, name, classes, visited, qualify))
    return frozenset(used)


def _index_serializer(
    name: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    qualify: Callable[[str, ast.expr], str],
    bindings: Mapping[str, Mapping[str, str]],
    serializers: set[str],
) -> None:
    parameter = function.args.args[0].arg
    local_names = {
        node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    } | {argument.arg for argument in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)}
    if "getattr" in local_names:
        return
    for comprehension in ast.walk(function):
        if not isinstance(comprehension, ast.DictComp | ast.ListComp) or len(comprehension.generators) != 1:
            continue
        if _serializer_comprehension(comprehension, name, parameter, local_names, bindings, qualify):
            serializers.add(f"{name}.{function.name}")


def _serializer_comprehension(
    comprehension: ast.DictComp | ast.ListComp,
    name: str,
    parameter: str,
    local_names: set[str],
    bindings: Mapping[str, Mapping[str, str]],
    qualify: Callable[[str, ast.expr], str],
) -> bool:
    generator = comprehension.generators[0]
    if not _fields_generator(generator, name, parameter, local_names, qualify) or not isinstance(
        generator.target, ast.Name
    ):
        return False
    value = comprehension.value if isinstance(comprehension, ast.DictComp) else comprehension.elt
    return any(
        _field_getattr(call, parameter, generator.target.id, "getattr" in bindings[name]) for call in ast.walk(value)
    )


def _fields_generator(
    generator: ast.comprehension,
    name: str,
    parameter: str,
    local_names: set[str],
    qualify: Callable[[str, ast.expr], str],
) -> bool:
    iterator = generator.iter
    return (
        isinstance(generator.target, ast.Name)
        and not generator.ifs
        and isinstance(iterator, ast.Call)
        and qualify(name, iterator.func) == "dataclasses.fields"
        and not (isinstance(iterator.func, ast.Name) and iterator.func.id in local_names)
        and len(iterator.args) == 1
        and isinstance(iterator.args[0], ast.Name)
        and iterator.args[0].id == parameter
    )


def _field_getattr(call: ast.AST, parameter: str, target: str, shadowed: bool) -> bool:
    if not isinstance(call, ast.Call) or not _getattr_call(call, shadowed):
        return False
    receiver, field = call.args
    return (
        isinstance(receiver, ast.Name)
        and receiver.id == parameter
        and isinstance(field, ast.Attribute)
        and field.attr == "name"
        and isinstance(field.value, ast.Name)
        and field.value.id == target
    )


def _nested_classes(
    annotation: ast.expr,
    name: str,
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    visited: set[str],
    qualify: Callable[[str, ast.expr], str],
) -> list[str]:
    return [
        nested
        for part in ast.walk(annotation)
        if isinstance(part, ast.Name | ast.Attribute)
        and (nested := qualify(name, part)) in classes
        and nested not in visited
    ]


def _getattr_call(call: ast.AST, shadowed: bool) -> bool:
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "getattr"
        and not shadowed
        and len(call.args) == 2
    )
