"""Read explicit receiver types from defining modules for qualified consumer checks."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass

from .unreachable_frameworks import _expression_name, _import_bindings
from .unreachable_models import ShippedModule


@dataclass(frozen=True)
class ReceiverTypes:
    """Constructed module values and explicitly declared callable return types."""

    values: Mapping[str, str]
    returns: Mapping[str, str]
    classes: frozenset[str]
    fields: Mapping[str, str]
    contexts: Mapping[str, str]


def _qualify(node: ast.expr, name: str, bindings: Mapping[str, str]) -> str:
    spelling = _expression_name(node)
    head, separator, tail = spelling.partition(".")
    return f"{bindings.get(head, f'{name}.{head}')}{separator}{tail}"


def receiver_types(
    modules: Mapping[str, ShippedModule], *, known_classes: frozenset[str] = frozenset()
) -> ReceiverTypes:
    """Resolve declared factories and constants without importing their modules."""
    classes = known_classes | frozenset(
        f"{name}.{node.name}"
        for name, module in modules.items()
        for node in module.tree.body
        if isinstance(node, ast.ClassDef)
    )
    values: dict[str, str] = {}
    returns: dict[str, str] = {}
    fields: dict[str, str] = {}
    contexts: dict[str, str] = {}
    for name, module in modules.items():
        bindings = _import_bindings(module)

        for owner in module.tree.body:
            if isinstance(owner, ast.ClassDef):
                for member in owner.body:
                    if isinstance(member, ast.AnnAssign) and isinstance(member.target, ast.Name):
                        target = _qualify(member.annotation, name, bindings)
                        if target in classes:
                            fields[f"{name}.{owner.name}.{member.target.id}"] = target
            functions = owner.body if isinstance(owner, ast.ClassDef) else [owner]
            for function in functions:
                if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef) or function.returns is None:
                    continue
                annotation = function.returns
                if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
                    annotation = ast.parse(annotation.value, mode="eval").body
                result = _qualify(annotation, name, bindings)
                if isinstance(owner, ast.ClassDef) and _expression_name(annotation) == "Self":
                    result = f"{name}.{owner.name}"
                if result in classes:
                    prefix = f"{name}.{owner.name}." if isinstance(owner, ast.ClassDef) else f"{name}."
                    returns[prefix + function.name] = result
                    if any(_expression_name(decorator) == "property" for decorator in function.decorator_list):
                        fields[prefix + function.name] = result
                if isinstance(annotation, ast.Subscript) and any(
                    _qualify(decorator, name, bindings)
                    in {"contextlib.contextmanager", "contextlib.asynccontextmanager"}
                    for decorator in function.decorator_list
                ):
                    yielded = _qualify(annotation.slice, name, bindings)
                    if yielded in classes:
                        prefix = f"{name}.{owner.name}." if isinstance(owner, ast.ClassDef) else f"{name}."
                        contexts[prefix + function.name] = yielded
            if isinstance(owner, ast.Assign | ast.AnnAssign) and isinstance(owner.value, ast.Call):
                result = _qualify(owner.value.func, name, bindings)
                targets = owner.targets if isinstance(owner, ast.Assign) else [owner.target]
                if result in classes:
                    values.update((f"{name}.{target.id}", result) for target in targets if isinstance(target, ast.Name))
    return ReceiverTypes(values, returns, classes, fields, contexts)
