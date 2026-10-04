"""Resolve fields consumed by live Pydantic schemas without executing product code."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from dev.quality.source_import_analysis import resolve_relative_import

from .unreachable_frameworks import FrameworkContract, _expression_name, _import_bindings
from .unreachable_members import resolved_calls
from .unreachable_models import ShippedModule
from .unreachable_schema_consumers import schema_parameter_consumers

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
    bindings = {name: _import_bindings(module) for name, module in modules.items()}
    for name, module in modules.items():
        candidates: dict[str, set[str]] = {}
        for statement in ast.walk(module.tree):
            if isinstance(statement, ast.ImportFrom):
                base = resolve_relative_import(name, module.is_package, statement.level, statement.module)
                if base:
                    for alias in statement.names:
                        candidates.setdefault(alias.asname or alias.name, set()).add(f"{base}.{alias.name}")
        # Ambiguous local bindings cannot prove a qualified consumer.
        for alias, targets in candidates.items():
            if len(targets) == 1:
                bindings[name][alias] = next(iter(targets))
            else:
                bindings[name].pop(alias, None)
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
    factories = {
        f"{target}.{method.name}"
        for target, (_, node) in classes.items()
        if target in models
        for method in node.body
        if isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef)
        and method.returns is not None
        and _expression_name(method.returns).rsplit(".", 1)[-1] in {"Self", node.name}
        and any(_expression_name(decorator) == "classmethod" for decorator in method.decorator_list)
    }

    def qualify(name: str, expression: ast.expr) -> str:
        target = _expression_name(expression)
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

    schema_parameters = schema_parameter_consumers(modules, qualify)
    pending: list[str] = []
    for name in reachable:
        for call in resolved_calls(modules[name], frozenset(modules)):
            target = call.target
            for parameter, candidate in call.keywords:
                if parameter in schema_parameters.get(target, ()) and candidate in models:
                    pending.append(candidate)
            if target == "pydantic.TypeAdapter":
                pending.extend(candidate for candidate in call.arguments if candidate in schema_targets)
            if target.rsplit(".", 1)[-1] in _SCHEMA_METHODS or target in factories:
                target = target.rsplit(".", 1)[0]
            if target in models:
                pending.append(target)
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
        if target not in models:
            # An enum used as a field is validated as a whole, not by dot access.
            if any(
                _expression_name(base).rsplit(".", 1)[-1] in {"Enum", "StrEnum", "IntEnum", "Flag", "IntFlag"}
                for base in node.bases
            ):
                for statement in node.body:
                    if isinstance(statement, ast.Assign):
                        used.update(
                            (name, f"{node.name}.{item.id}") for item in statement.targets if isinstance(item, ast.Name)
                        )
            continue
        for base in node.bases:
            parent = qualify(name, base)
            if parent in models:
                pending.append(parent)
        for statement in node.body:
            if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
                continue
            annotation = statement.annotation
            if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                annotation = ast.parse(annotation.value, mode="eval").body
            if any(
                isinstance(part, ast.Name | ast.Attribute) and _expression_name(part).rsplit(".", 1)[-1] == "ClassVar"
                for part in ast.walk(annotation)
            ):
                continue
            used.add((name, f"{node.name}.{statement.target.id}"))
            for part in ast.walk(annotation):
                if isinstance(part, ast.Name | ast.Attribute):
                    nested = qualify(name, part)
                    if nested in classes or nested in aliases:
                        pending.append(nested)
    return frozenset(used)
