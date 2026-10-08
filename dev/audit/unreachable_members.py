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
    whole_uses: set[str] | None = None,
) -> set[tuple[str, str]]:
    """Keep member identities qualified; a same-named attribute cannot clear one.

    Only imported classes, constructor assignments and explicit annotations
    establish an owner. Arbitrary call results and unresolved receivers remain
    candidates. Scope-local names do not escape into sibling functions.
    """
    uses: set[tuple[str, str]] = set()

    def expression(node: ast.expr, bindings: dict[str, str], containers: dict[str, str] | None = None) -> str:
        if isinstance(node, ast.Name):
            target = bindings.get(node.id, "")
            return receivers.values.get(target, target) if receivers is not None else target
        if isinstance(node, ast.Attribute):
            owner = expression(node.value, bindings, containers)
            if receivers is not None:
                owner = receivers.fields.get(owner, owner)
            return f"{owner}.{node.attr}" if owner else ""
        if isinstance(node, ast.Call) and receivers is not None:
            return receivers.returns.get(expression(node.func, bindings, containers), "")
        if isinstance(node, ast.Subscript):
            if (
                not isinstance(node.slice, ast.Slice)
                and isinstance(node.value, ast.Name)
                and containers
                and (item_type := containers.get(node.value.id))
            ):
                return item_type
            return expression(node.value, bindings, containers)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                parsed = ast.parse(node.value, mode="eval").body
            except SyntaxError:
                return ""
            return expression(parsed, bindings, containers)
        return ""

    def narrow(condition: ast.expr, bindings: dict[str, str]) -> None:
        """Use an explicit builtin isinstance guard, never an arbitrary predicate."""
        if (
            receivers is not None
            and isinstance(condition, ast.Call)
            and isinstance(condition.func, ast.Name)
            and condition.func.id == "isinstance"
            and "isinstance" not in bindings
            and len(condition.args) == 2
            and isinstance(condition.args[0], ast.Name)
            and (owner := expression(condition.args[1], bindings)) in receivers.classes
        ):
            bindings[condition.args[0].id] = owner

    def element(node: ast.expr, bindings: dict[str, str], containers: dict[str, str]) -> str:
        if receivers is None:
            return ""
        if isinstance(node, ast.Name) and node.id in containers:
            return containers[node.id]
        if isinstance(node, ast.ListComp | ast.SetComp | ast.GeneratorExp) and len(node.generators) == 1:
            generator = node.generators[0]
            if not isinstance(generator.target, ast.Name):
                return ""
            local = dict(bindings)
            local[generator.target.id] = element(generator.iter, bindings, containers)
            for condition in generator.ifs:
                narrow(condition, local)
            result = expression(node.elt, local, containers)
            return result if result in receivers.classes else ""
        target = expression(node.func if isinstance(node, ast.Call) else node, bindings, containers)
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
                    local[argument.arg] = ""
                    local_containers.pop(argument.arg, None)
                    if argument.arg in {"self", "cls"} and class_owner:
                        local[argument.arg] = class_owner
                    if argument.annotation is not None:
                        owner = expression(argument.annotation, bindings, containers)
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
                    owner = expression(node.annotation, bindings, containers)
                if not owner and isinstance(value, ast.Call):
                    owner = expression(value.func, bindings, containers)
                    if receivers is not None:
                        owner = receivers.returns.get(owner, owner)
                if not owner and isinstance(value, ast.Name | ast.Subscript):
                    owner = expression(value, bindings, containers)
                item_type = element(value, bindings, containers) if value is not None else ""
                if isinstance(node, ast.AnnAssign) and receivers is not None:
                    item_type = iterable_receiver_type(node.annotation, module.name, bindings, receivers.classes)
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = ""
                        containers.pop(target.id, None)
                        if owner and not item_type:
                            bindings[target.id] = owner
                        if item_type:
                            containers[target.id] = item_type
            elif isinstance(node, ast.For | ast.AsyncFor):
                if whole_uses is not None:
                    whole_uses.add(expression(node.iter, bindings, containers))
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
                        owner = receivers.contexts.get(expression(item.context_expr.func, bindings, containers))
                        if owner:
                            bindings[item.optional_vars.id] = owner

            def visit_expression(part: ast.AST, scoped: dict[str, str]) -> None:
                if isinstance(part, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                    local = dict(scoped)
                    for generator in part.generators:
                        if whole_uses is not None:
                            whole_uses.add(expression(generator.iter, local, containers))
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
                            narrow(condition, local)
                    results = (part.key, part.value) if isinstance(part, ast.DictComp) else (part.elt,)
                    for result in results:
                        for inner in _expression_nodes(result):
                            visit_expression(inner, local)
                    return
                if isinstance(part, ast.Attribute):
                    target = expression(part, scoped, containers)
                    parts = target.split(".")
                    for end in range(len(parts) - 2, 0, -1):
                        owner = ".".join(parts[:end])
                        if owner in known:
                            uses.add((owner, ".".join(parts[end:])))
                            break
                elif calls is not None and isinstance(part, ast.Call):
                    calls.append(
                        ResolvedCall(
                            expression(part.func, scoped, containers),
                            tuple(
                                (keyword.arg, expression(keyword.value, scoped, containers))
                                for keyword in part.keywords
                            ),
                            frozenset(
                                expression(item, scoped, containers)
                                for argument in part.args
                                for item in (argument, *ast.walk(argument))
                                if isinstance(item, ast.Name | ast.Attribute | ast.Call)
                            ),
                            tuple(expression(argument, scoped, containers) for argument in part.args),
                        )
                    )

            for part in _expression_nodes(node):
                visit_expression(part, bindings)
            for block in ("body", "orelse", "finalbody"):
                children = getattr(node, block, None)
                if isinstance(children, list):
                    walk(children, child_bindings, inherited_containers=containers)
            for handler in getattr(node, "handlers", ()):
                handler_bindings = dict(bindings)
                if handler.name:
                    handler_bindings[handler.name] = ""
                walk(handler.body, handler_bindings, inherited_containers=containers)

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
