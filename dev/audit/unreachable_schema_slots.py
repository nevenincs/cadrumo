"""Follow class payload declarations into proven schema-building parameters."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from .unreachable_frameworks import _import_bindings
from .unreachable_models import ShippedModule
from .unreachable_schema_consumers import SchemaParameters


def schema_slot_payloads(
    modules: Mapping[str, ShippedModule],
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    models: frozenset[str],
    reachable: frozenset[str],
    qualify: Callable[[str, ast.expr], str],
    parameters: Mapping[str, SchemaParameters],
    constructed: frozenset[str],
) -> frozenset[str]:
    """A registered slot counts only when a live owner's getter reaches a schema factory."""
    shadowed_getattr_by_module = {
        name: "getattr" in _import_bindings(module)
        or any(
            (isinstance(part, ast.Name) and part.id == "getattr" and isinstance(part.ctx, ast.Store))
            or (isinstance(part, ast.FunctionDef | ast.ClassDef) and part.name == "getattr")
            for part in ast.walk(module.tree)
        )
        for name, module in modules.items()
        if name in reachable
    }
    getters: dict[str, tuple[str, str]] = {}
    model_getters: dict[str, str] = {}
    for owner, (name, node) in classes.items():
        if name not in reachable:
            continue
        for method in node.body:
            if not isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            aliases: dict[str, str] = {}
            rebound: set[str] = set()

            def slot(
                expression: ast.expr | None,
                aliases: Mapping[str, str] = aliases,
                name: str = name,
                arguments: ast.arguments = method.args,
                shadowed_getattr: bool = shadowed_getattr_by_module[name],
            ) -> str:
                if isinstance(expression, ast.Name):
                    return aliases.get(expression.id, "")
                if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
                    return expression.attr if expression.value.id in {"self", "cls"} else ""
                if isinstance(expression, ast.Call):
                    if qualify(name, expression.func) == "typing.cast" and len(expression.args) == 2:
                        return slot(expression.args[1])
                    if (
                        isinstance(expression.func, ast.Name)
                        and expression.func.id == "getattr"
                        and len(expression.args) >= 2
                        and isinstance(expression.args[0], ast.Name)
                        and expression.args[0].id in {"self", "cls"}
                        and isinstance(expression.args[1], ast.Constant)
                        and isinstance(expression.args[1].value, str)
                        and not shadowed_getattr
                        and not any(argument.arg == "getattr" for argument in arguments.args)
                    ):
                        return expression.args[1].value
                return ""

            returns: list[str] = []
            for statement in ast.walk(method):
                if isinstance(statement, ast.Assign | ast.AnnAssign):
                    targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
                    for target in targets:
                        if not isinstance(target, ast.Name):
                            continue
                        value = slot(statement.value)
                        if target.id in aliases or target.id in rebound:
                            aliases.pop(target.id, None)
                            rebound.add(target.id)
                        elif value:
                            aliases[target.id] = value
                elif isinstance(statement, ast.Return):
                    returns.append(slot(statement.value))
            if returns and all(returns) and len(set(returns)) == 1:
                getters[f"{owner}.{method.name}"] = (owner, returns[0])
            returned_models = [
                qualify(name, part.value)
                for part in ast.walk(method)
                if isinstance(part, ast.Return) and part.value is not None
            ]
            if returned_models and len(set(returned_models)) == 1 and returned_models[0] in models:
                model_getters[f"{owner}.{method.name}"] = returned_models[0]

    consumed_getters: dict[str, set[str]] = {}
    for owner, (name, node) in classes.items():
        if name not in reachable:
            continue
        for method in node.body:
            if not isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for call in (part for part in ast.walk(method) if isinstance(part, ast.Call)):
                destination = qualify(name, call.func)
                consumed = parameters.get(destination)
                if consumed is None:
                    continue
                values = [call.args[index] for index in consumed.positionals if index < len(call.args)]
                values.extend(keyword.value for keyword in call.keywords if keyword.arg in consumed.keywords)
                for value in values:
                    if (
                        not isinstance(value, ast.Call)
                        or not isinstance(value.func, ast.Attribute)
                        or not isinstance(value.func.value, ast.Name)
                        or value.func.value.id not in {"self", "cls"}
                    ):
                        continue
                    getter = getters.get(f"{owner}.{value.func.attr}")
                    if getter is not None or f"{owner}.{value.func.attr}" in model_getters:
                        consumed_getters.setdefault(owner, set()).add(value.func.attr)

    def inherited_getters(owner: str, seen: frozenset[str] = frozenset()) -> frozenset[str]:
        if owner in seen or owner not in classes:
            return frozenset[str]()
        name, node = classes[owner]
        methods = set(consumed_getters.get(owner, ()))
        for base in node.bases:
            parent = qualify(name, base.value if isinstance(base, ast.Subscript) else base)
            methods.update(inherited_getters(parent, seen | {owner}))
        return frozenset(methods)

    def resolved_getter(owner: str, method: str, seen: frozenset[str] = frozenset()) -> tuple[str, str] | None:
        if owner in seen or owner not in classes:
            return None
        name, node = classes[owner]
        if any(isinstance(part, ast.FunctionDef | ast.AsyncFunctionDef) and part.name == method for part in node.body):
            target = f"{owner}.{method}"
            return model_getters.get(target, ""), getters.get(target, ("", ""))[1]
        for base in node.bases:
            parent = qualify(name, base.value if isinstance(base, ast.Subscript) else base)
            value = resolved_getter(parent, method, seen | {owner})
            if value is not None:
                return value
        return None

    payloads: set[str] = set()
    for owner in constructed & classes.keys():
        name, node = classes[owner]
        slots: set[str] = set()
        for method in inherited_getters(owner):
            value = resolved_getter(owner, method)
            if value is None:
                continue
            payload, slot_name = value
            if payload:
                payloads.add(payload)
            if slot_name:
                slots.add(slot_name)
        for statement in node.body:
            if (
                not isinstance(statement, ast.AnnAssign)
                or not isinstance(statement.target, ast.Name)
                or statement.target.id not in slots
                or statement.value is None
            ):
                continue
            if not any(
                isinstance(part, ast.Name | ast.Attribute) and qualify(name, part) == "typing.ClassVar"
                for part in ast.walk(statement.annotation)
            ):
                continue
            payload = qualify(name, statement.value)
            if payload in models:
                payloads.add(payload)
    return frozenset(payloads)
