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
    fields: dict[str, set[str]] = {}
    for name, module in modules.items():
        for owner in module.tree.body:
            if not isinstance(owner, ast.ClassDef) or f"{name}.{owner.name}" not in models:
                continue
            fields[f"{name}.{owner.name}"] = {
                member.target.id
                for member in owner.body
                if isinstance(member, ast.AnnAssign)
                and isinstance(member.target, ast.Name)
                and isinstance(member.annotation, ast.Subscript)
                and ast.unparse(member.annotation.value) == "type"
                and qualify(name, member.annotation.slice) in models | {"pydantic.BaseModel", "pydantic.main.BaseModel"}
            }
    validated: dict[str, set[str]] = {}
    for name, prefix, function, _arguments in functions.values():
        if not fields.get(prefix) or not any(
            qualify(name, decorator.func if isinstance(decorator, ast.Call) else decorator)
            in {"pydantic.field_validator", "pydantic.model_validator"}
            for decorator in function.decorator_list
        ):
            continue
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
            if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            value = node.value
            if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute) or value.func.attr != "get":
                continue
            mapping = value.func.value
            if isinstance(mapping, ast.BoolOp) and isinstance(mapping.op, ast.Or) and len(mapping.values) == 2:
                fallback = mapping.values[1]
                if not isinstance(fallback, ast.Dict) or fallback.keys:
                    continue
                mapping = mapping.values[0]
            if (
                isinstance(mapping, ast.Attribute)
                and mapping.attr == "data"
                and isinstance(mapping.value, ast.Name)
                and mapping.value.id in infos
                and not stores.get(mapping.value.id)
                and value.args
                and isinstance(value.args[0], ast.Constant)
                and isinstance(value.args[0].value, str)
                and value.args[0].value in fields[prefix]
                and stores.get(node.targets[0].id) == 1
            ):
                aliases[node.targets[0].id] = value.args[0].value
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            head = call.func
            while isinstance(head, ast.Attribute):
                head = head.value
            if isinstance(head, ast.Name) and (head.id in arguments or stores.get(head.id)):
                continue
            destination = qualify(name, call.func)
            if destination not in functions:
                continue
            parameters = functions[destination][3]
            bindings = dict(zip(parameters, call.args, strict=False))
            bindings.update((keyword.arg, keyword.value) for keyword in call.keywords if keyword.arg is not None)
            validated.setdefault(prefix, set()).update(
                aliases[value.id]
                for parameter, value in bindings.items()
                if parameter in consumed[destination] and isinstance(value, ast.Name) and value.id in aliases
            )
    result: dict[str, set[str]] = {}
    for target, (_name, prefix, function, _arguments) in functions.items():
        if (
            not validated.get(prefix)
            or not any(ast.unparse(decorator) == "classmethod" for decorator in function.decorator_list)
            or any(
                isinstance(node, ast.Name) and node.id == "cls" and isinstance(node.ctx, ast.Store)
                for node in ast.walk(function)
            )
        ):
            continue
        for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
            if (
                not isinstance(call.func, ast.Attribute)
                or not isinstance(call.func.value, ast.Name)
                or call.func.value.id != "cls"
                or call.func.attr != "model_validate"
                or not call.args
                or not isinstance(call.args[0], ast.Dict)
            ):
                continue
            payload = call.args[0]
            result.setdefault(target, set()).update(
                value.id
                for key, value in zip(payload.keys, payload.values, strict=True)
                if isinstance(key, ast.Constant)
                and key.value in validated[prefix]
                and isinstance(value, ast.Name)
                and value.id in typed[target]
            )
    return result
