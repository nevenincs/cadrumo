"""Resolve member consumers on imported classes and explicitly typed local bindings."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass

from dev.quality.source_import_analysis import resolve_relative_import

from .unreachable_frameworks import _import_bindings
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import ReceiverTypes, iterable_receiver_type


@dataclass(frozen=True)
class ResolvedCall:
    """A call's qualified receiver and statically named argument types."""

    target: str
    keywords: tuple[tuple[str | None, str], ...]
    arguments: frozenset[str]
    positionals: tuple[str, ...]


def _expression_nodes(node: ast.AST) -> Iterator[ast.AST]:
    yield node
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return
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

    def element(node: ast.expr, bindings: dict[str, str], containers: dict[str, str]) -> str:
        if receivers is None:
            return ""
        if isinstance(node, ast.Name) and node.id in containers:
            return containers[node.id]
        target = expression(node.func if isinstance(node, ast.Call) else node, bindings)
        return receivers.iterables.get(target, "")

    def walk(
        nodes: list[ast.stmt],
        inherited: dict[str, str],
        class_owner: str = "",
        inherited_containers: dict[str, str] | None = None,
    ) -> None:
        bindings = dict(inherited)
        containers = dict(inherited_containers or {})
        for node in nodes:
            child_bindings = bindings
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
                local_containers = dict(containers)
                arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                for argument in arguments:
                    local.pop(argument.arg, None)
                    local_containers.pop(argument.arg, None)
                    if argument.arg in {"self", "cls"} and class_owner:
                        local[argument.arg] = class_owner
                    if argument.annotation is not None:
                        owner = expression(argument.annotation, bindings)
                        if owner:
                            local[argument.arg] = owner
                        if receivers is not None:
                            item_type = iterable_receiver_type(
                                argument.annotation, module.name, bindings, receivers.classes
                            )
                            if item_type:
                                local_containers[argument.arg] = item_type
                walk(node.body, local, inherited_containers=local_containers)
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
                        containers.pop(target.id, None)
                        if owner:
                            bindings[target.id] = owner
                        item_type = element(value, bindings, containers) if value is not None else ""
                        if isinstance(node, ast.AnnAssign) and receivers is not None:
                            item_type = iterable_receiver_type(
                                node.annotation, module.name, bindings, receivers.classes
                            )
                        if item_type:
                            containers[target.id] = item_type
            elif isinstance(node, ast.For | ast.AsyncFor):
                child_bindings = dict(bindings)
                if isinstance(node.target, ast.Name):
                    child_bindings.pop(node.target.id, None)
                    item_type = element(node.iter, bindings, containers)
                    if item_type:
                        child_bindings[node.target.id] = item_type
            elif isinstance(node, ast.With | ast.AsyncWith) and receivers is not None:
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call) and isinstance(item.optional_vars, ast.Name):
                        bindings.pop(item.optional_vars.id, None)
                        owner = receivers.contexts.get(expression(item.context_expr.func, bindings))
                        if owner:
                            bindings[item.optional_vars.id] = owner

            def visit_expression(part: ast.AST, scoped: dict[str, str]) -> None:
                if isinstance(part, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                    local = dict(scoped)
                    for generator in part.generators:
                        for inner in _expression_nodes(generator.iter):
                            visit_expression(inner, local)
                        if isinstance(generator.target, ast.Name):
                            item_type = element(generator.iter, local, containers)
                            local.pop(generator.target.id, None)
                            if item_type:
                                local[generator.target.id] = item_type
                        for condition in generator.ifs:
                            for inner in _expression_nodes(condition):
                                visit_expression(inner, local)
                    results = (part.key, part.value) if isinstance(part, ast.DictComp) else (part.elt,)
                    for result in results:
                        for inner in _expression_nodes(result):
                            visit_expression(inner, local)
                    return
                if isinstance(part, ast.Attribute):
                    target = expression(part, scoped)
                    parts = target.split(".")
                    for end in range(len(parts) - 2, 0, -1):
                        owner = ".".join(parts[:end])
                        if owner in known:
                            uses.add((owner, ".".join(parts[end:])))
                            break
                elif calls is not None and isinstance(part, ast.Call):
                    calls.append(
                        ResolvedCall(
                            expression(part.func, scoped),
                            tuple((keyword.arg, expression(keyword.value, scoped)) for keyword in part.keywords),
                            frozenset(
                                expression(item, scoped)
                                for argument in part.args
                                for item in (argument, *ast.walk(argument))
                                if isinstance(item, ast.Name | ast.Attribute | ast.Call)
                            ),
                            tuple(expression(argument, scoped) for argument in part.args),
                        )
                    )

            for part in _expression_nodes(node):
                visit_expression(part, bindings)
            for block in ("body", "orelse", "finalbody"):
                children = getattr(node, block, None)
                if isinstance(children, list):
                    walk(children, child_bindings, inherited_containers=containers)

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
