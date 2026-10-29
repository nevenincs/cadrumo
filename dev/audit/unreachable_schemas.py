"""Resolve fields consumed by live Pydantic schemas without executing product code."""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping

from dev.quality.source_import_analysis import resolve_relative_import

from .unreachable_frameworks import FrameworkContract, expression_name, import_bindings
from .unreachable_member_models import ResolvedCall
from .unreachable_members import resolved_calls
from .unreachable_models import ShippedModule
from .unreachable_schema_consumers import SchemaParameters, schema_parameter_consumers
from .unreachable_schema_slots import schema_slot_payloads

_SCHEMA_METHODS = frozenset({"model_validate", "model_validate_json", "model_json_schema", "model_construct"})


def schema_member_uses(
    modules: Mapping[str, ShippedModule],
    reachable: frozenset[str],
    contracts: Mapping[str, Mapping[str, FrameworkContract]],
) -> frozenset[tuple[str, str]]:
    """Follow constructed/validated models through their declared nested field types.

    Importing a model alone does not consume its fields. Once a reachable caller
    constructs or validates it, Pydantic reads every field declaration, including
    defaults and enum alternatives. Ordinary methods, unannotated constants and
    ClassVars remain independently auditable.
    """
    bindings = _schema_bindings(modules)
    classes, aliases, schema_targets, models, factories = _schema_declarations(modules, contracts)

    def qualify(name: str, expression: ast.expr) -> str:
        target = expression_name(expression)
        head, separator, tail = target.partition(".")
        target = f"{bindings[name].get(head, f'{name}.{head}')}{separator}{tail}"
        followed: set[str] = set()
        while target not in followed:
            followed.add(target)
            owner, _, member = target.rpartition(".")
            rebound = bindings.get(owner, {}).get(member)
            if rebound is None or rebound == target:
                break
            target = rebound
        return target

    schema_parameters = schema_parameter_consumers(modules, qualify, frozenset(models))
    pending, constructed = _call_targets(
        modules, reachable, classes, schema_parameters, schema_targets, models, factories
    )
    pending.extend(
        schema_slot_payloads(
            modules, classes, frozenset(models), reachable, qualify, schema_parameters, frozenset(constructed)
        )
    )
    used = _walk_schema_targets(pending, classes, aliases, models, schema_targets, qualify)
    return frozenset(used)


def _schema_bindings(modules: Mapping[str, ShippedModule]) -> dict[str, dict[str, str]]:
    bindings = {name: import_bindings(module) for name, module in modules.items()}
    for name, module in modules.items():
        candidates = _import_candidates(name, module)
        # Ambiguous local bindings cannot prove a qualified consumer.
        for alias, targets in candidates.items():
            if len(targets) == 1:
                bindings[name][alias] = next(iter(targets))
            else:
                bindings[name].pop(alias, None)
    return bindings


def _call_targets(
    modules: Mapping[str, ShippedModule],
    reachable: frozenset[str],
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    schema_parameters: Mapping[str, SchemaParameters],
    schema_targets: set[str],
    models: set[str],
    factories: set[str],
) -> tuple[list[str], set[str]]:
    pending: list[str] = []
    constructed: set[str] = set()
    for name in reachable:
        for call in resolved_calls(modules[name], frozenset(modules)):
            _collect_call_targets(
                call, classes, schema_parameters, schema_targets, models, factories, pending, constructed
            )
    return pending, constructed


def _walk_schema_targets(
    pending: list[str],
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    aliases: Mapping[str, tuple[str, ast.expr]],
    models: set[str],
    schema_targets: set[str],
    qualify: Callable[[str, ast.expr], str],
) -> set[tuple[str, str]]:
    used: set[tuple[str, str]] = set()
    visited: set[str] = set()
    while pending:
        target = pending.pop()
        if target in visited:
            continue
        visited.add(target)
        if target in aliases:
            name, expression = aliases[target]
            pending.extend(
                qualify(name, part)
                for part in ast.walk(expression)
                if isinstance(part, ast.Name | ast.Attribute) and qualify(name, part) in schema_targets
            )
            continue
        if target not in classes:
            continue
        name, node = classes[target]
        _collect_class_fields(target, name, node, models, classes, aliases, qualify, pending, used)
    return used


def _schema_declarations(
    modules: Mapping[str, ShippedModule], contracts: Mapping[str, Mapping[str, FrameworkContract]]
) -> tuple[dict[str, tuple[str, ast.ClassDef]], dict[str, tuple[str, ast.expr]], set[str], set[str], set[str]]:
    classes = {
        f"{name}.{node.name}": (name, node)
        for name, module in modules.items()
        for node in module.tree.body
        if isinstance(node, ast.ClassDef)
    }
    aliases = {
        f"{name}.{node.name.id}": (name, node.value)
        for name, module in modules.items()
        for node in module.tree.body
        if isinstance(node, ast.TypeAlias)
    }
    schema_targets = classes.keys() | aliases.keys()
    models = {
        f"{name}.{owner}"
        for name, owners in contracts.items()
        for owner, contract in owners.items()
        if contract.pydantic
    }
    factories = _model_factories(classes, models)
    return classes, aliases, schema_targets, models, factories


def _import_candidates(name: str, module: ShippedModule) -> dict[str, set[str]]:
    candidates: dict[str, set[str]] = {}
    for statement in ast.walk(module.tree):
        if isinstance(statement, ast.ImportFrom):
            base = resolve_relative_import(name, module.is_package, statement.level, statement.module)
            if base is not None and base:
                for alias in statement.names:
                    candidates.setdefault(alias.asname or alias.name, set()).add(f"{base}.{alias.name}")
    return candidates


def _collect_call_targets(
    call: ResolvedCall,
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    schema_parameters: Mapping[str, SchemaParameters],
    schema_targets: set[str],
    models: set[str],
    factories: set[str],
    pending: list[str],
    constructed: set[str],
) -> None:
    target = call.target
    if target in classes:
        constructed.add(target)
    parameters = schema_parameters.get(target)
    _consumer_arguments(call, parameters, models, pending)
    if target == "pydantic.TypeAdapter":
        pending.extend(candidate for candidate in call.arguments if candidate in schema_targets)
    if target.rsplit(".", 1)[-1] in _SCHEMA_METHODS or target in factories:
        target = target.rsplit(".", 1)[0]
    if target in models:
        pending.append(target)


def _collect_class_fields(
    target: str,
    name: str,
    node: ast.ClassDef,
    models: set[str],
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    aliases: Mapping[str, tuple[str, ast.expr]],
    qualify: Callable[[str, ast.expr], str],
    pending: list[str],
    used: set[tuple[str, str]],
) -> None:
    if target not in models:
        _enum_fields(name, node, used)
        return
    for base in node.bases:
        parent = qualify(name, base)
        if parent in models:
            pending.append(parent)
    _model_fields(name, node, classes, aliases, qualify, pending, used)


def _model_factories(classes: Mapping[str, tuple[str, ast.ClassDef]], models: set[str]) -> set[str]:
    factories = {
        f"{target}.{method.name}"
        for target, (_, node) in classes.items()
        if target in models
        for method in node.body
        if isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef)
        and method.returns is not None
        and expression_name(method.returns).rsplit(".", 1)[-1] in {"Self", node.name}
        and any(expression_name(decorator) == "classmethod" for decorator in method.decorator_list)
    }

    return factories


def _consumer_arguments(
    call: ResolvedCall, parameters: SchemaParameters | None, models: set[str], pending: list[str]
) -> None:
    if parameters is not None:
        pending.extend(
            candidate
            for parameter, candidate in call.keywords
            if parameter in parameters.keywords and candidate in models
        )
        pending.extend(
            call.positionals[index]
            for index in parameters.positionals
            if index < len(call.positionals) and call.positionals[index] in models
        )


def _enum_fields(name: str, node: ast.ClassDef, used: set[tuple[str, str]]) -> None:
    # An enum used as a field is validated as a whole, not by dot access.
    if any(
        expression_name(base).rsplit(".", 1)[-1] in {"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag"}
        for base in node.bases
    ):
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                used.update(
                    (name, f"{node.name}.{item.id}") for item in statement.targets if isinstance(item, ast.Name)
                )


def _model_fields(
    name: str,
    node: ast.ClassDef,
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    aliases: Mapping[str, tuple[str, ast.expr]],
    qualify: Callable[[str, ast.expr], str],
    pending: list[str],
    used: set[tuple[str, str]],
) -> None:
    for statement in node.body:
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
            continue
        annotation = statement.annotation
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            annotation = ast.parse(annotation.value, mode="eval").body
        if _is_class_variable(annotation):
            continue
        used.add((name, f"{node.name}.{statement.target.id}"))
        _nested_types(annotation, name, classes, aliases, qualify, pending)


def _is_class_variable(annotation: ast.expr) -> bool:
    return any(
        isinstance(part, ast.Name | ast.Attribute) and expression_name(part).rsplit(".", 1)[-1] == "ClassVar"
        for part in ast.walk(annotation)
    )


def _nested_types(
    annotation: ast.expr,
    name: str,
    classes: Mapping[str, tuple[str, ast.ClassDef]],
    aliases: Mapping[str, tuple[str, ast.expr]],
    qualify: Callable[[str, ast.expr], str],
    pending: list[str],
) -> None:
    for part in ast.walk(annotation):
        if isinstance(part, ast.Name | ast.Attribute):
            nested = qualify(name, part)
            if nested in classes or nested in aliases:
                pending.append(nested)
