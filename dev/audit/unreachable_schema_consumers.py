"""Follow typed schema parameters to actual validation and schema operations."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .unreachable_models import ShippedModule
from .unreachable_schema_validators import SchemaFunction, validator_schema_arguments

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
    functions, typed, consumed = _indexed_functions(modules, qualify, models)
    _propagate_consumers(modules, qualify, models, functions, typed, consumed)
    return _parameter_coordinates(functions, consumed)


def _indexed_functions(
    modules: Mapping[str, ShippedModule], qualify: Callable[[str, ast.expr], str], models: frozenset[str]
) -> tuple[dict[str, SchemaFunction], dict[str, set[str]], dict[str, set[str]]]:
    functions: dict[str, SchemaFunction] = {}
    typed: dict[str, set[str]] = {}
    consumed: dict[str, set[str]] = {}
    for name, module in modules.items():
        for owner in module.tree.body:
            for function in owner.body if isinstance(owner, ast.ClassDef) else [owner]:
                if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                _index_function(name, owner, function, qualify, models, functions, typed, consumed)
    return functions, typed, consumed


def _propagate_consumers(
    modules: Mapping[str, ShippedModule],
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
    functions: Mapping[str, SchemaFunction],
    typed: Mapping[str, set[str]],
    consumed: dict[str, set[str]],
) -> None:
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
                changed |= _forwarded_call(call, target, name, prefix, functions, typed, consumed, qualify)


def _parameter_coordinates(
    functions: Mapping[str, SchemaFunction], consumed: Mapping[str, set[str]]
) -> dict[str, SchemaParameters]:
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


def _index_function(
    name: str,
    owner: ast.stmt,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
    functions: dict[str, SchemaFunction],
    typed: dict[str, set[str]],
    consumed: dict[str, set[str]],
) -> None:
    arguments = (*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs)
    prefix = f"{name}.{owner.name}" if isinstance(owner, ast.ClassDef) else name
    target = prefix + "." + function.name
    functions[target] = (name, prefix, function, tuple(argument.arg for argument in arguments))
    bounds = {
        parameter.name: qualify(name, parameter.bound)
        for parameter in (*getattr(owner, "type_params", ()), *function.type_params)
        if isinstance(parameter, ast.TypeVar) and parameter.bound is not None
    }

    typed[target], consumed[target] = _schema_usage(arguments, function, bounds, name, qualify, models)


def _schema_usage(
    arguments: tuple[ast.arg, ...],
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    bounds: Mapping[str, str],
    name: str,
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
) -> tuple[set[str], set[str]]:
    rebound = {part.id for part in ast.walk(function) if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)}
    typed_parameters = {
        argument.arg
        for argument in arguments
        if argument.arg not in rebound
        and _type_target(argument.annotation, bounds, name, qualify)
        in models | {"pydantic.BaseModel", "pydantic.main.BaseModel"}
    }
    consumed_parameters = _direct_schema_consumers(
        function, arguments, rebound, bounds, name, qualify, models, typed_parameters
    )
    return typed_parameters, consumed_parameters


def _direct_schema_consumers(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    arguments: tuple[ast.arg, ...],
    rebound: set[str],
    bounds: Mapping[str, str],
    name: str,
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
    typed_parameters: set[str],
) -> set[str]:
    consumed_parameters = {
        used_name for part in ast.walk(function) if (used_name := _schema_operation(part, typed_parameters)) is not None
    }
    _class_getitem_consumers(
        function, arguments, rebound, bounds, name, qualify, models, typed_parameters, consumed_parameters
    )
    return consumed_parameters


def _class_getitem_consumers(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    arguments: tuple[ast.arg, ...],
    rebound: set[str],
    bounds: Mapping[str, str],
    name: str,
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
    typed_parameters: set[str],
    consumed_parameters: set[str],
) -> None:
    schema_receivers = _schema_receivers(arguments, rebound, bounds, name, qualify, models)
    for call in (part for part in ast.walk(function) if isinstance(part, ast.Call)):
        if not _schema_getitem(call, schema_receivers):
            continue
        consumed_parameters.update(
            argument.id for argument in call.args if isinstance(argument, ast.Name) and argument.id in typed_parameters
        )


def _type_target(
    annotation: ast.expr | None, bounds: Mapping[str, str], name: str, qualify: Callable[[str, ast.expr], str]
) -> str:
    if not isinstance(annotation, ast.Subscript) or ast.unparse(annotation.value) != "type":
        return ""
    value = annotation.slice
    if isinstance(value, ast.Subscript):
        value = value.value
    return bounds.get(ast.unparse(value), qualify(name, value))


def _forwarded_call(
    call: ast.Call,
    target: str,
    name: str,
    prefix: str,
    functions: Mapping[str, SchemaFunction],
    typed: Mapping[str, set[str]],
    consumed: dict[str, set[str]],
    qualify: Callable[[str, ast.expr], str],
) -> bool:
    destination = qualify(name, call.func)
    destination = _receiver_destination(call, prefix, destination)
    if destination not in functions:
        return False
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
    return len(consumed[target]) != previous


def _receiver_destination(call: ast.Call, prefix: str, destination: str) -> str:
    if (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in {"cls", "self"}
    ):
        return prefix + "." + call.func.attr
    return destination


def _schema_operation(part: ast.AST, typed_parameters: set[str]) -> str | None:
    if (
        isinstance(part, ast.Attribute)
        and isinstance(part.value, ast.Name)
        and part.attr in _OPERATIONS
        and part.value.id in typed_parameters
    ):
        return part.value.id
    return None


def _schema_getitem(call: ast.Call, receivers: set[str]) -> bool:
    return (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "__class_getitem__"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in receivers
    )


def _schema_receivers(
    arguments: tuple[ast.arg, ...],
    rebound: set[str],
    bounds: Mapping[str, str],
    name: str,
    qualify: Callable[[str, ast.expr], str],
    models: frozenset[str],
) -> set[str]:
    schema_receivers = {
        argument.arg
        for argument in arguments
        if argument.arg not in rebound and _type_target(argument.annotation, bounds, name, qualify) in models
    }
    return schema_receivers
