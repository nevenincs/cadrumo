"""Follow model-class payloads through registered Pydantic validation hooks."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from .unreachable_models import ShippedModule

type SchemaFunction = tuple[str, str, ast.FunctionDef | ast.AsyncFunctionDef, tuple[str, ...]]


def validator_schema_arguments(
    modules: Mapping[str, ShippedModule],
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
    functions: Mapping[str, SchemaFunction],
    typed: Mapping[str, set[str]],
    consumed: Mapping[str, set[str]],
) -> dict[str, set[str]]:
    """A model-class field is consumed only when its validator reaches a schema sink."""
    fields = _model_class_fields(modules, qualify, models)
    validated = _validated_fields(fields, functions, qualify, consumed)
    result = _schema_payloads(validated, functions, typed)
    return result


def _model_class_fields(
    modules: Mapping[str, ShippedModule], qualify: Callable[[str, ast.expr], str], models: frozenset[str]
) -> dict[str, set[str]]:
    fields: dict[str, set[str]] = {}
    for name, module in modules.items():
        for owner in module.tree.body:
            if not isinstance(owner, ast.ClassDef) or f"{name}.{owner.name}" not in models:
                continue
            fields[f"{name}.{owner.name}"] = {
                field for member in owner.body if (field := _model_field(member, name, qualify, models)) is not None
            }
    return fields


def _validated_fields(
    fields: Mapping[str, set[str]],
    functions: Mapping[str, SchemaFunction],
    qualify: Callable[[str, ast.expr], str],
    consumed: Mapping[str, set[str]],
) -> dict[str, set[str]]:
    validated: dict[str, set[str]] = {}
    for name, prefix, function, _arguments in functions.values():
        if not bool(fields.get(prefix)) or not any(
            qualify(name, decorator.func if isinstance(decorator, ast.Call) else decorator)
            in {"pydantic.field_validator", "pydantic.model_validator"}
            for decorator in function.decorator_list
        ):
            continue
        _infos, arguments, stores, aliases = _validator_aliases(name, prefix, function, fields, qualify)
        _consume_aliases(name, prefix, function, arguments, stores, aliases, functions, qualify, consumed, validated)
    return validated


def _schema_payloads(
    validated: Mapping[str, set[str]], functions: Mapping[str, SchemaFunction], typed: Mapping[str, set[str]]
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for target, (_name, prefix, function, _arguments) in functions.items():
        if (
            not bool(validated.get(prefix))
            or not any(ast.unparse(decorator) == "classmethod" for decorator in function.decorator_list)
            or any(
                isinstance(node, ast.Name) and node.id == "cls" and isinstance(node.ctx, ast.Store)
                for node in ast.walk(function)
            )
        ):
            continue
        _collect_payloads(function, prefix, target, validated, typed, result)
    return result


def _validator_aliases(
    name: str,
    prefix: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    fields: Mapping[str, set[str]],
    qualify: Callable[[str, ast.expr], str],
) -> tuple[set[str], set[str], dict[str, int], dict[str, str]]:
    infos = {
        argument.arg
        for argument in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
        if argument.annotation is not None and qualify(name, argument.annotation) == "pydantic.ValidationInfo"
    }
    arguments = {
        argument.arg for argument in (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
    }
    stores: dict[str, int] = {}
    for node in ast.walk(function):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
    aliases: dict[str, str] = {}
    for node in ast.walk(function):
        alias = _data_alias(node, infos, stores, fields[prefix])
        if alias is not None:
            aliases[alias[0]] = alias[1]
    return infos, arguments, stores, aliases


def _consume_aliases(
    name: str,
    prefix: str,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    arguments: set[str],
    stores: Mapping[str, int],
    aliases: Mapping[str, str],
    functions: Mapping[str, SchemaFunction],
    qualify: Callable[[str, ast.expr], str],
    consumed: Mapping[str, set[str]],
    validated: dict[str, set[str]],
) -> None:
    for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
        if _shadowed_call(call, arguments, stores):
            continue
        destination = qualify(name, call.func)
        if destination not in functions:
            continue
        parameters = functions[destination][3]
        bindings = dict(zip(parameters, call.args, strict=False))
        bindings.update((keyword.arg, keyword.value) for keyword in call.keywords if keyword.arg is not None)
        _record_bindings(prefix, bindings, aliases, consumed[destination], validated)


def _collect_payloads(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    prefix: str,
    target: str,
    validated: Mapping[str, set[str]],
    typed: Mapping[str, set[str]],
    result: dict[str, set[str]],
) -> None:
    for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
        payload = _class_payload(call)
        if payload is None:
            continue
        result.setdefault(target, set()).update(
            value.id
            for key, value in zip(payload.keys, payload.values, strict=True)
            if isinstance(key, ast.Constant)
            and key.value in validated[prefix]
            and isinstance(value, ast.Name)
            and value.id in typed[target]
        )


def _data_alias(node: ast.AST, infos: set[str], stores: Mapping[str, int], fields: set[str]) -> tuple[str, str] | None:
    if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
        return None
    value = node.value
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute) or value.func.attr != "get":
        return None
    mapping = _fallback_mapping(value.func.value)
    if mapping is None:
        return None
    if not _validation_data(mapping, infos, stores):
        return None
    return _field_alias(value, node.targets[0].id, fields, stores)


def _validation_data(mapping: ast.expr, infos: set[str], stores: Mapping[str, int]) -> bool:
    return (
        isinstance(mapping, ast.Attribute)
        and mapping.attr == "data"
        and isinstance(mapping.value, ast.Name)
        and mapping.value.id in infos
        and not bool(stores.get(mapping.value.id))
    )


def _class_payload(call: ast.Call) -> ast.Dict | None:
    if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
        return None
    if call.func.value.id != "cls" or call.func.attr != "model_validate" or not call.args:
        return None
    return call.args[0] if isinstance(call.args[0], ast.Dict) else None


def _record_bindings(
    prefix: str,
    bindings: Mapping[str, ast.expr],
    aliases: Mapping[str, str],
    consumed: set[str],
    validated: dict[str, set[str]],
) -> None:
    validated.setdefault(prefix, set()).update(
        aliases[value.id]
        for parameter, value in bindings.items()
        if parameter in consumed and isinstance(value, ast.Name) and value.id in aliases
    )


def _model_field(
    member: ast.stmt, name: str, qualify: Callable[[str, ast.expr], str], models: frozenset[str]
) -> str | None:
    if not isinstance(member, ast.AnnAssign) or not isinstance(member.target, ast.Name):
        return None
    if not isinstance(member.annotation, ast.Subscript) or ast.unparse(member.annotation.value) != "type":
        return None
    if qualify(name, member.annotation.slice) not in models | {"pydantic.BaseModel", "pydantic.main.BaseModel"}:
        return None
    return member.target.id


def _shadowed_call(call: ast.Call, arguments: set[str], stores: Mapping[str, int]) -> bool:
    head = call.func
    while isinstance(head, ast.Attribute):
        head = head.value
    return isinstance(head, ast.Name) and (head.id in arguments or bool(stores.get(head.id)))


def _fallback_mapping(mapping: ast.expr) -> ast.expr | None:
    if isinstance(mapping, ast.BoolOp) and isinstance(mapping.op, ast.Or) and len(mapping.values) == 2:
        fallback = mapping.values[1]
        if not isinstance(fallback, ast.Dict) or fallback.keys:
            return None
        mapping = mapping.values[0]
    return mapping


def _field_alias(value: ast.Call, target: str, fields: set[str], stores: Mapping[str, int]) -> tuple[str, str] | None:
    if not value.args or not isinstance(value.args[0], ast.Constant) or not isinstance(value.args[0].value, str):
        return None
    field = value.args[0].value
    if field not in fields or stores.get(target) != 1:
        return None
    return target, field
