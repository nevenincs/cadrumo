"""Recognize actual whole-record dataclass reads, including field-walking serializers."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .unreachable_frameworks import _expression_name, _import_bindings
from .unreachable_members import resolved_calls
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import receiver_types


def dataclass_member_uses(
    modules: Mapping[str, ShippedModule], reachable: frozenset[str]
) -> frozenset[tuple[str, str]]:
    """A constructor alone cannot prove that a dataclass's fields are consumed."""
    bindings = {name: _import_bindings(module) for name, module in modules.items()}

    def qualify(name: str, node: ast.expr) -> str:
        spelling = _expression_name(node)
        head, separator, tail = spelling.partition(".")
        return f"{bindings[name].get(head, f'{name}.{head}')}{separator}{tail}"

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
    serializers: set[str] = {"dataclasses.asdict", "dataclasses.astuple"}
    for name in reachable:
        for function in modules[name].tree.body:
            if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef) or not function.args.args:
                continue
            parameter = function.args.args[0].arg
            local_names = {
                node.id for node in ast.walk(function) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
            } | {
                argument.arg
                for argument in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
            }
            if "getattr" in local_names:
                continue
            for comprehension in ast.walk(function):
                if not isinstance(comprehension, ast.DictComp | ast.ListComp) or len(comprehension.generators) != 1:
                    continue
                generator = comprehension.generators[0]
                if (
                    not isinstance(generator.target, ast.Name)
                    or generator.ifs
                    or not isinstance(generator.iter, ast.Call)
                    or qualify(name, generator.iter.func) != "dataclasses.fields"
                    or (isinstance(generator.iter.func, ast.Name) and generator.iter.func.id in local_names)
                    or len(generator.iter.args) != 1
                    or not isinstance(generator.iter.args[0], ast.Name)
                    or generator.iter.args[0].id != parameter
                ):
                    continue
                value = comprehension.value if isinstance(comprehension, ast.DictComp) else comprehension.elt
                for call in ast.walk(value):
                    if (
                        isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Name)
                        and call.func.id == "getattr"
                        and "getattr" not in bindings[name]
                        and len(call.args) == 2
                        and isinstance(call.args[0], ast.Name)
                        and call.args[0].id == parameter
                        and isinstance(call.args[1], ast.Attribute)
                        and call.args[1].attr == "name"
                        and isinstance(call.args[1].value, ast.Name)
                        and call.args[1].value.id == generator.target.id
                    ):
                        serializers.add(f"{name}.{function.name}")
    receivers = receiver_types(modules)
    pending = [
        argument
        for name in reachable
        for call in resolved_calls(modules[name], frozenset(modules), receivers)
        if call.target in serializers
        for argument in call.arguments
        if argument in classes
    ]
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
            pending.extend(
                nested
                for part in ast.walk(member.annotation)
                if isinstance(part, ast.Name | ast.Attribute)
                and (nested := qualify(name, part)) in classes
                and nested not in visited
            )
    return frozenset(used)
