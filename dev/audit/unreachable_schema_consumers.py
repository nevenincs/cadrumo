"""Follow typed schema parameters to actual validation and schema operations."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .unreachable_models import ShippedModule
from .unreachable_schema_validators import validator_schema_arguments

_OPERATIONS = frozenset(
    {"model_validate", "model_validate_json", "model_json_schema", "model_construct", "model_fields"}
)


@dataclass(frozen=True)
class SchemaParameters:
    """Exact keyword names and positional coordinates consumed by a schema call."""

    keywords: frozenset[str]
    positionals: tuple[int, ...]


def schema_parameter_consumers(
    modules: Mapping[str, ShippedModule], qualify: Callable[[str, ast.expr], str], models: frozenset[str]
) -> dict[str, SchemaParameters]:
    """A type annotation alone is insufficient: the parameter must reach Pydantic.

    Forwarders inherit only the consumed argument positions of an already proven
    consumer. An unused parameter or a diagnostic print does not consume a schema.
    """
    functions: dict[str, tuple[str, str, ast.FunctionDef | ast.AsyncFunctionDef, tuple[str, ...]]] = {}
    typed: dict[str, set[str]] = {}
    consumed: dict[str, set[str]] = {}
    for name, module in modules.items():
        for owner in module.tree.body:
            for function in owner.body if isinstance(owner, ast.ClassDef) else [owner]:
                if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                arguments = (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
                prefix = f"{name}.{owner.name}" if isinstance(owner, ast.ClassDef) else name
                target = prefix + "." + function.name
                functions[target] = (name, prefix, function, tuple(argument.arg for argument in arguments))
                bounds = {
                    parameter.name: qualify(name, parameter.bound)
                    for parameter in (*getattr(owner, "type_params", ()), *function.type_params)
                    if isinstance(parameter, ast.TypeVar) and parameter.bound is not None
                }

                def type_target(
                    annotation: ast.expr | None, bounds: Mapping[str, str] = bounds, name: str = name
                ) -> str:
                    if not isinstance(annotation, ast.Subscript) or ast.unparse(annotation.value) != "type":
                        return ""
                    value = annotation.slice
                    if isinstance(value, ast.Subscript):
                        value = value.value
                    return bounds.get(ast.unparse(value), qualify(name, value))

                rebound = {
                    part.id
                    for part in ast.walk(function)
                    if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)
                }
                typed[target] = {
                    argument.arg
                    for argument in arguments
                    if argument.arg not in rebound
                    and type_target(argument.annotation) in models | {"pydantic.BaseModel", "pydantic.main.BaseModel"}
                }
                consumed[target] = {
                    part.value.id
                    for part in ast.walk(function)
                    if isinstance(part, ast.Attribute)
                    and isinstance(part.value, ast.Name)
                    and part.attr in _OPERATIONS
                    and part.value.id in typed[target]
                }
                schema_receivers = {
                    argument.arg
                    for argument in arguments
                    if argument.arg not in rebound and type_target(argument.annotation) in models
                }
                for call in (part for part in ast.walk(function) if isinstance(part, ast.Call)):
                    if not isinstance(call.func, ast.Attribute) or call.func.attr != "__class_getitem__":
                        continue
                    if not isinstance(call.func.value, ast.Name) or call.func.value.id not in schema_receivers:
                        continue
                    consumed[target].update(
                        argument.id
                        for argument in call.args
                        if isinstance(argument, ast.Name) and argument.id in typed[target]
                    )
    changed = True
    while changed:
        changed = False
        for target, parameters in validator_schema_arguments(
            modules, qualify, models, functions, typed, consumed
        ).items():
            previous = len(consumed[target])
            consumed[target].update(parameters)
            changed |= len(consumed[target]) != previous
        for target, (name, prefix, function, _arguments) in functions.items():
            for call in (part for part in ast.walk(function) if isinstance(part, ast.Call)):
                destination = qualify(name, call.func)
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in {"cls", "self"}
                ):
                    destination = prefix + "." + call.func.attr
                if destination not in functions:
                    continue
                destination_arguments = functions[destination][3]
                if destination_arguments and destination_arguments[0] in {"cls", "self"}:
                    destination_arguments = destination_arguments[1:]
                bindings = dict(zip(destination_arguments, call.args, strict=False))
                bindings.update((keyword.arg, keyword.value) for keyword in call.keywords if keyword.arg is not None)
                forwarded = {
                    value.id
                    for parameter, value in bindings.items()
                    if parameter in consumed[destination] and isinstance(value, ast.Name) and value.id in typed[target]
                }
                previous = len(consumed[target])
                consumed[target].update(forwarded)
                changed |= len(consumed[target]) != previous
    result: dict[str, SchemaParameters] = {}
    for target, (_name, _prefix, function, arguments) in functions.items():
        positional = tuple(argument.arg for argument in (*function.args.posonlyargs, *function.args.args))
        if positional and positional[0] in {"self", "cls"}:
            positional = positional[1:]
        result[target] = SchemaParameters(
            frozenset(parameter for parameter in arguments if parameter in consumed[target]),
            tuple(index for index, parameter in enumerate(positional) if parameter in consumed[target]),
        )
    return result
