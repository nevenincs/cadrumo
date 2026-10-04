"""Follow typed schema parameters to actual validation and schema operations."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from .unreachable_models import ShippedModule

_OPERATIONS = frozenset(
    {"model_validate", "model_validate_json", "model_json_schema", "model_construct", "model_fields"}
)


def schema_parameter_consumers(
    modules: Mapping[str, ShippedModule], qualify: Callable[[str, ast.expr], str]
) -> dict[str, tuple[str, ...]]:
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
                typed[target] = {
                    argument.arg
                    for argument in arguments
                    if isinstance(argument.annotation, ast.Subscript)
                    and ast.unparse(argument.annotation.value) == "type"
                    and qualify(name, argument.annotation.slice) in {"pydantic.BaseModel", "pydantic.main.BaseModel"}
                }
                consumed[target] = {
                    part.value.id
                    for part in ast.walk(function)
                    if isinstance(part, ast.Attribute)
                    and isinstance(part.value, ast.Name)
                    and part.attr in _OPERATIONS
                    and part.value.id in typed[target]
                }
    changed = True
    while changed:
        changed = False
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
    return {
        target: tuple(parameter for parameter in record[3] if parameter in consumed[target])
        for target, record in functions.items()
    }
