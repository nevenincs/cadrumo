"""Resolve member consumers on imported classes and explicitly typed local bindings."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass

from dev.quality.source_import_analysis import resolve_relative_import

from .unreachable_frameworks import _import_bindings
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import ReceiverTypes


@dataclass(frozen=True)
class ResolvedCall:
    """A call's qualified receiver and statically named argument types."""

    target: str
    keywords: tuple[tuple[str | None, str], ...]
    arguments: frozenset[str]


def _expression_nodes(node: ast.AST) -> Iterator[ast.AST]:
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, ast.stmt):
            yield from _expression_nodes(child)


def resolved_member_uses(
    module: ShippedModule,
    known: frozenset[str],
    *,
    calls: list[ResolvedCall] | None = None,
    receivers: ReceiverTypes | None = None,
) -> set[tuple[str, str]]:
    """Keep member identities qualified; a same-named attribute cannot clear one.

    Only imported classes, constructor assignments and explicit annotations
    establish an owner. Arbitrary call results and unresolved receivers remain
    candidates. Scope-local names do not escape into sibling functions.
    """
    uses: set[tuple[str, str]] = set()

    def expression(node: ast.expr, bindings: dict[str, str]) -> str:
        if isinstance(node, ast.Name):
            target = bindings.get(node.id, "")
            return receivers.values.get(target, target) if receivers is not None else target
        if isinstance(node, ast.Attribute):
            owner = expression(node.value, bindings)
            if receivers is not None:
                owner = receivers.fields.get(owner, owner)
            return f"{owner}.{node.attr}" if owner else ""
        if isinstance(node, ast.Call) and receivers is not None:
            return receivers.returns.get(expression(node.func, bindings), "")
        if isinstance(node, ast.Subscript):
            return expression(node.value, bindings)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                parsed = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return ""
            return expression(parsed, bindings)
        return ""

    def walk(nodes: list[ast.stmt], inherited: dict[str, str], class_owner: str = "") -> None:
        bindings = dict(inherited)
        for node in nodes:
            if isinstance(node, ast.ImportFrom):
                base = resolve_relative_import(module.name, module.is_package, node.level, node.module)
                if base:
                    bindings.update((alias.asname or alias.name, f"{base}.{alias.name}") for alias in node.names)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    bindings[alias.asname or alias.name.split(".")[0]] = (
                        alias.name if alias.asname else alias.name.split(".")[0]
                    )
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                local = dict(bindings)
                arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                for argument in arguments:
                    local.pop(argument.arg, None)
                    if argument.arg in {"self", "cls"} and class_owner:
                        local[argument.arg] = class_owner
                    if argument.annotation is not None:
                        owner = expression(argument.annotation, bindings)
                        if owner:
                            local[argument.arg] = owner
                walk(node.body, local)
                continue
            elif isinstance(node, ast.ClassDef):
                bindings[node.name] = f"{module.name}.{node.name}"
                walk(node.body, bindings, f"{module.name}.{node.name}")
                continue
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                value = node.value
                owner = ""
                if isinstance(node, ast.AnnAssign):
                    owner = expression(node.annotation, bindings)
                if not owner and isinstance(value, ast.Call):
                    owner = expression(value.func, bindings)
                    if receivers is not None:
                        owner = receivers.returns.get(owner, owner)
                if not owner and isinstance(value, ast.Name):
                    owner = expression(value, bindings)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings.pop(target.id, None)
                        if owner:
                            bindings[target.id] = owner
            elif isinstance(node, ast.With | ast.AsyncWith) and receivers is not None:
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call) and isinstance(item.optional_vars, ast.Name):
                        bindings.pop(item.optional_vars.id, None)
                        owner = receivers.contexts.get(expression(item.context_expr.func, bindings))
                        if owner:
                            bindings[item.optional_vars.id] = owner
            for part in _expression_nodes(node):
                if isinstance(part, ast.Attribute):
                    target = expression(part, bindings)
                    parts = target.split(".")
                    for end in range(len(parts) - 2, 0, -1):
                        owner = ".".join(parts[:end])
                        if owner in known:
                            uses.add((owner, ".".join(parts[end:])))
                            break
                elif calls is not None and isinstance(part, ast.Call):
                    calls.append(
                        ResolvedCall(
                            expression(part.func, bindings),
                            tuple((keyword.arg, expression(keyword.value, bindings)) for keyword in part.keywords),
                            frozenset(
                                expression(item, bindings)
                                for argument in part.args
                                for item in (argument, *ast.walk(argument))
                                if isinstance(item, ast.Name | ast.Attribute | ast.Call)
                            ),
                        )
                    )
            for block in ("body", "orelse", "finalbody"):
                children = getattr(node, block, None)
                if isinstance(children, list):
                    walk(children, bindings)

    initial = _import_bindings(module)
    initial.update(
        (node.name, f"{module.name}.{node.name}")
        for node in module.tree.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    )
    walk(module.tree.body, initial)
    return uses


def resolved_calls(
    module: ShippedModule, known: frozenset[str], receivers: ReceiverTypes | None = None
) -> tuple[ResolvedCall, ...]:
    """Resolve callable and argument identities using the same lexical scope walk."""
    calls: list[ResolvedCall] = []
    resolved_member_uses(module, known, calls=calls, receivers=receivers)
    return tuple(calls)
