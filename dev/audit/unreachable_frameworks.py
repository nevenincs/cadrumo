"""Resolve inherited framework contracts without importing shipped product modules."""

from __future__ import annotations

import ast
import ctypes
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from typing import Final

from dev.quality.source_import_analysis import resolve_relative_import

from .unreachable_models import ShippedModule

_INSTALLED_FRAMEWORK_MODULES: Final = (
    "click",
    "click.core",
    "ctypes",
    "logging",
    "pydantic",
    "pydantic.main",
    "pydantic_settings",
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.types",
    "textual.app",
    "textual.command",
    "textual.containers",
    "textual.dom",
    "textual.message",
    "textual.message_pump",
    "textual.screen",
    "textual.scroll_view",
    "textual.widget",
    "textual.widgets",
    "typer",
    "typer._click.types",
    "typer.core",
)


@dataclass(frozen=True)
class FrameworkContract:
    """Members declared by installed bases, and Textual's dispatch convention."""

    members: frozenset[str] = frozenset()
    textual: bool = False
    pydantic: bool = False


def _expression_name(node: ast.expr) -> str:
    if isinstance(node, ast.Subscript):
        return _expression_name(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _expression_name(node.value)
        return f"{owner}.{node.attr}" if owner else ""
    return ""


def _import_bindings(module: ShippedModule) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for node in module.tree.body:
        if isinstance(node, ast.ImportFrom):
            base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
            if base:
                bindings.update((alias.asname or alias.name, f"{base}.{alias.name}") for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bindings[alias.asname or alias.name.split(".")[0]] = (
                    alias.name if alias.asname else alias.name.split(".")[0]
                )
        elif isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
            original = _expression_name(node.value)
            if not original:
                continue
            head, separator, tail = original.partition(".")
            qualified = f"{bindings.get(head, f'{module.name}.{head}')}{separator}{tail}"
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    bindings[target.id] = qualified
    return bindings


def _installed_contract(target: str) -> FrameworkContract:
    """Consult only supported dependency families; product imports never execute."""
    module_name, _, class_name = target.rpartition(".")
    if module_name.split(".")[0] not in {
        "textual",
        "sqlalchemy",
        "pydantic",
        "pydantic_settings",
        "ctypes",
        "logging",
        "click",
        "typer",
    }:
        return FrameworkContract()
    for installed_module in _INSTALLED_FRAMEWORK_MODULES:
        if installed_module == module_name:
            base = getattr(import_module(installed_module), class_name, None)
            break
    else:
        raise ValueError(f"framework contract requires an explicitly declared installed module: {module_name}")
    if not isinstance(base, type):
        return FrameworkContract()
    members: set[str] = set()
    for ancestor in base.__mro__:
        if ancestor is object:
            continue
        members.update(vars(ancestor))
        members.update(vars(ancestor).get("__annotations__", {}))
    if issubclass(base, (ctypes.Structure, ctypes.Union)):
        members.add("_fields_")
    textual = any(ancestor.__module__ == "textual.dom" and ancestor.__name__ == "DOMNode" for ancestor in base.__mro__)
    pydantic = any(
        ancestor.__module__ == "pydantic.main" and ancestor.__name__ == "BaseModel" for ancestor in base.__mro__
    )
    return FrameworkContract(frozenset(members), textual, pydantic)


def framework_contracts(modules: Mapping[str, ShippedModule]) -> dict[str, dict[str, FrameworkContract]]:
    """Follow aliased imports and local inheritance back to installed base declarations."""
    classes = {
        (name, node.name): node
        for name, module in modules.items()
        for node in module.tree.body
        if isinstance(node, ast.ClassDef)
    }
    bindings = {name: _import_bindings(module) for name, module in modules.items()}
    resolved: dict[tuple[str, str], FrameworkContract] = {}
    installed: dict[str, FrameworkContract] = {}
    parents: dict[tuple[str, str], set[tuple[str, str]]] = {}

    def resolve(key: tuple[str, str], visiting: frozenset[tuple[str, str]]) -> FrameworkContract:
        if key in resolved:
            return resolved[key]
        if key in visiting:
            return FrameworkContract()
        node = classes[key]
        members: set[str] = set()
        textual = False
        pydantic = False
        for base in node.bases:
            target = _expression_name(base)
            head, separator, tail = target.partition(".")
            bound = bindings[key[0]].get(head)
            qualified = f"{bound}{separator}{tail}" if bound else f"{key[0]}.{target}"
            followed: set[str] = set()
            while qualified not in followed:
                followed.add(qualified)
                owner, _, name = qualified.rpartition(".")
                rebound = bindings.get(owner, {}).get(name)
                if rebound is None or rebound == qualified:
                    break
                qualified = rebound
            owner, _, name = qualified.rpartition(".")
            if (owner, name) in classes:
                parents.setdefault(key, set()).add((owner, name))
                contract = resolve((owner, name), visiting | {key})
            else:
                if qualified not in installed:
                    installed[qualified] = _installed_contract(qualified)
                contract = installed[qualified]
            members.update(contract.members)
            textual |= contract.textual
            pydantic |= contract.pydantic
        result = FrameworkContract(frozenset(members), textual, pydantic)
        resolved[key] = result
        return result

    for key in classes:
        resolve(key, frozenset())
    pending = list(resolved)
    while pending:
        child = pending.pop()
        contract = resolved[child]
        for parent in parents.get(child, ()):
            inherited = resolved[parent]
            merged = FrameworkContract(
                inherited.members | contract.members,
                inherited.textual or contract.textual,
                inherited.pydantic or contract.pydantic,
            )
            if merged != inherited:
                resolved[parent] = merged
                pending.append(parent)
    by_module: dict[str, dict[str, FrameworkContract]] = {}
    for key, contract in resolved.items():
        by_module.setdefault(key[0], {})[key[1]] = contract
    return by_module
