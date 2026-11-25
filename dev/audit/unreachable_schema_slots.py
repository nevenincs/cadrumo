"""Follow class payload declarations into proven schema-building parameters."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from .unreachable_frameworks import import_bindings
from .unreachable_models import ShippedModule
from .unreachable_schema_consumers import SchemaParameters
from .unreachable_slot_expression import slot_expression


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
    getters, model_getters = _getters(modules, classes, models, reachable, qualify)
    consumed_getters = _consumed_getters(classes, reachable, qualify, parameters, getters, model_getters)
    return _slot_payloads(classes, models, constructed, qualify, getters, model_getters, consumed_getters)


def _getters(
    modules: Mapping[str, ShippedModule],
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    models: frozenset[str],
    reachable: frozenset[str],
    qualify: Callable[[str, ast.expr], str],
) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    shadowed_getattr_by_module = {
        name: _shadows_getattr(module) for name, module in modules.items() if name in reachable
    }
    getters: dict[str, tuple[str, str]] = {}
    model_getters: dict[str, str] = {}
    for owner, (name, node) in classes.items():
        if name not in reachable:
            continue
        for method in node.body:
            if not isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            _index_getter(
                owner, name, method, shadowed_getattr_by_module[name], qualify, models, getters, model_getters
            )
    return getters, model_getters


def _consumed_getters(
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    reachable: frozenset[str],
    qualify: Callable[[str, ast.expr], str],
    parameters: Mapping[str, SchemaParameters],
    getters: Mapping[str, tuple[str, str]],
    model_getters: Mapping[str, str],
) -> dict[str, set[str]]:
    consumed_getters: dict[str, set[str]] = {}
    for owner, (name, node) in classes.items():
        if name not in reachable:
            continue
        for method in node.body:
            if not isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for call in (part for part in ast.walk(method) if isinstance(part, ast.Call)):
                _consume_getter_call(owner, name, call, qualify, parameters, getters, model_getters, consumed_getters)
    return consumed_getters


def _slot_payloads(
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    models: frozenset[str],
    constructed: frozenset[str],
    qualify: Callable[[str, ast.expr], str],
    getters: Mapping[str, tuple[str, str]],
    model_getters: Mapping[str, str],
    consumed_getters: Mapping[str, set[str]],
) -> frozenset[str]:
    payloads: set[str] = set()
    for owner in constructed & classes.keys():
        _collect_owner_payloads(owner, classes, models, qualify, getters, model_getters, consumed_getters, payloads)
    return frozenset(payloads)


def _index_getter(
    owner: str,
    name: str,
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    shadowed_getattr: bool,
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
    getters: dict[str, tuple[str, str]],
    model_getters: dict[str, str],
) -> None:
    aliases: dict[str, str] = {}
    rebound: set[str] = set()

    returns = _getter_returns(method, aliases, rebound, name, shadowed_getattr, qualify)
    if returns and all(returns) and len(set(returns)) == 1:
        getters[f"{owner}.{method.name}"] = (owner, returns[0])
    returned_models = [
        qualify(name, part.value)
        for part in ast.walk(method)
        if isinstance(part, ast.Return) and part.value is not None
    ]
    if returned_models and len(set(returned_models)) == 1 and returned_models[0] in models:
        model_getters[f"{owner}.{method.name}"] = returned_models[0]


def _shadows_getattr(module: ShippedModule) -> bool:
    return "getattr" in import_bindings(module) or any(
        (isinstance(part, ast.Name) and part.id == "getattr" and isinstance(part.ctx, ast.Store))
        or (isinstance(part, ast.FunctionDef | ast.ClassDef) and part.name == "getattr")
        for part in ast.walk(module.tree)
    )


def _consume_getter_call(
    owner: str,
    name: str,
    call: ast.Call,
    qualify: Callable[[str, ast.expr], str],
    parameters: Mapping[str, SchemaParameters],
    getters: Mapping[str, tuple[str, str]],
    model_getters: Mapping[str, str],
    consumed_getters: dict[str, set[str]],
) -> None:
    destination = qualify(name, call.func)
    consumed = parameters.get(destination)
    if consumed is None:
        return
    values = [call.args[index] for index in consumed.positionals if index < len(call.args)]
    values.extend(keyword.value for keyword in call.keywords if keyword.arg in consumed.keywords)
    for value in values:
        method = _self_getter(value)
        if method is None:
            continue
        getter = getters.get(f"{owner}.{method}")
        if getter is not None or f"{owner}.{method}" in model_getters:
            consumed_getters.setdefault(owner, set()).add(method)


def _getter_returns(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    aliases: dict[str, str],
    rebound: set[str],
    name: str,
    shadowed_getattr: bool,
    qualify: Callable[[str, ast.expr], str],
) -> list[str]:
    returns: list[str] = []
    for statement in ast.walk(method):
        if isinstance(statement, ast.Assign | ast.AnnAssign):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                value = slot_expression(statement.value, aliases, name, method.args, shadowed_getattr, qualify)
                if target.id in aliases or target.id in rebound:
                    aliases.pop(target.id, None)
                    rebound.add(target.id)
                elif value:
                    aliases[target.id] = value
        elif isinstance(statement, ast.Return):
            returns.append(slot_expression(statement.value, aliases, name, method.args, shadowed_getattr, qualify))
    return returns


def _collect_owner_payloads(
    owner: str,
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    models: frozenset[str],
    qualify: Callable[[str, ast.expr], str],
    getters: Mapping[str, tuple[str, str]],
    model_getters: Mapping[str, str],
    consumed_getters: Mapping[str, set[str]],
    payloads: set[str],
) -> None:
    name, node = classes[owner]
    slots: set[str] = set()
    for method in _inherited_getters(owner, classes, consumed_getters, qualify):
        value = _resolved_getter(owner, method, classes, getters, model_getters, qualify)
        if value is None:
            continue
        payload, slot_name = value
        if payload:
            payloads.add(payload)
        if slot_name:
            slots.add(slot_name)
    for statement in node.body:
        value = _slot_value(statement, slots, name, qualify)
        if value is None:
            continue
        payload = qualify(name, value)
        if payload in models:
            payloads.add(payload)


def _self_getter(value: ast.expr) -> str | None:
    if (
        not isinstance(value, ast.Call)
        or not isinstance(value.func, ast.Attribute)
        or not isinstance(value.func.value, ast.Name)
    ):
        return None
    return value.func.attr if value.func.value.id in {"self", "cls"} else None


def _inherited_getters(
    owner: str,
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    consumed_getters: Mapping[str, set[str]],
    qualify: Callable[[str, ast.expr], str],
    seen: frozenset[str] = frozenset(),
) -> frozenset[str]:
    if owner in seen or owner not in classes:
        return frozenset[str]()
    name, node = classes[owner]
    methods = set(consumed_getters.get(owner, ()))
    for base in node.bases:
        parent = qualify(name, base.value if isinstance(base, ast.Subscript) else base)
        methods.update(_inherited_getters(parent, classes, consumed_getters, qualify, seen | {owner}))
    return frozenset(methods)


def _resolved_getter(
    owner: str,
    method: str,
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    getters: Mapping[str, tuple[str, str]],
    model_getters: Mapping[str, str],
    qualify: Callable[[str, ast.expr], str],
    seen: frozenset[str] = frozenset(),
) -> tuple[str, str] | None:
    if owner in seen or owner not in classes:
        return None
    name, node = classes[owner]
    if any(isinstance(part, ast.FunctionDef | ast.AsyncFunctionDef) and part.name == method for part in node.body):
        target = f"{owner}.{method}"
        return model_getters.get(target, ""), getters.get(target, ("", ""))[1]
    for base in node.bases:
        parent = qualify(name, base.value if isinstance(base, ast.Subscript) else base)
        value = _resolved_getter(parent, method, classes, getters, model_getters, qualify, seen | {owner})
        if value is not None:
            return value
    return None


def _is_classvar(annotation: ast.expr, name: str, qualify: Callable[[str, ast.expr], str]) -> bool:
    return any(
        isinstance(part, ast.Name | ast.Attribute) and qualify(name, part) == "typing.ClassVar"
        for part in ast.walk(annotation)
    )


def _slot_value(
    statement: ast.stmt, slots: set[str], name: str, qualify: Callable[[str, ast.expr], str]
) -> ast.expr | None:
    if (
        not isinstance(statement, ast.AnnAssign)
        or not isinstance(statement.target, ast.Name)
        or statement.target.id not in slots
        or statement.value is None
    ):
        return None
    return statement.value if _is_classvar(statement.annotation, name, qualify) else None
