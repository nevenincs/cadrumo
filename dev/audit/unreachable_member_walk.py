"""Walk lexical receiver and member uses without executing product code."""

from __future__ import annotations

import ast
from typing import cast

from dev.quality.source_import_analysis import resolve_relative_import

from .unreachable_member_expressions import MemberExpressionResolver, bind_targets
from .unreachable_member_models import ResolvedCall, expression_nodes
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import ReceiverTypes, iterable_receiver_type


class MemberWalk(MemberExpressionResolver):
    """Resolve member identities through lexical bindings."""

    def __init__(
        self,
        module: ShippedModule,
        known: frozenset[str],
        calls: list[ResolvedCall] | None,
        receivers: ReceiverTypes | None,
        whole_uses: set[str] | None,
    ) -> None:
        """Bind the audited module and optional collection sinks."""
        self.module = module
        self.known = known
        self.calls = calls
        super().__init__(receivers)
        self.whole_uses = whole_uses
        self.uses: set[tuple[str, str]] = set()

    def walk(
        self,
        nodes: list[ast.stmt],
        inherited: dict[str, str],
        class_owner: str = "",
        inherited_containers: dict[str, str] | None = None,
    ) -> None:
        """Walk statements in their lexical binding scope."""
        bindings = dict(inherited)
        containers = dict(inherited_containers or {})
        for node in nodes:
            child_bindings = bindings
            if isinstance(node, ast.ImportFrom):
                self._import_from(node, bindings)
            elif isinstance(node, ast.Import):
                self._import_names(node, bindings)
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                self._function_scope(node, bindings, containers, class_owner)
                continue
            elif isinstance(node, ast.ClassDef):
                bindings[node.name] = f"{self.module.name}.{node.name}"
                self.walk(node.body, bindings, f"{self.module.name}.{node.name}")
                continue
            elif isinstance(node, ast.Assign | ast.AnnAssign):
                self._assignment_scope(node, bindings, containers)
            elif isinstance(node, ast.For | ast.AsyncFor):
                child_bindings = self._loop_scope(node, bindings, containers)
            elif isinstance(node, ast.With | ast.AsyncWith):
                self._with_scope(node, bindings, containers)

            self._walk_children(node, bindings, child_bindings, containers)

    def _import_from(self, node: ast.ImportFrom, bindings: dict[str, str]) -> None:
        base = resolve_relative_import(self.module.name, self.module.is_package, node.level, node.module)
        if base is not None and base:
            bindings.update((alias.asname or alias.name, f"{base}.{alias.name}") for alias in node.names)

    def _import_names(self, node: ast.Import, bindings: dict[str, str]) -> None:
        for alias in node.names:
            bindings[alias.asname or alias.name.split(".")[0]] = (
                alias.name if (alias.asname is not None and alias.asname) else alias.name.split(".")[0]
            )

    def _walk_children(
        self, node: ast.stmt, bindings: dict[str, str], child_bindings: dict[str, str], containers: dict[str, str]
    ) -> None:
        for part in expression_nodes(node):
            self._visit_expression(part, bindings, containers)
        for block in ("body", "orelse", "finalbody"):
            children = getattr(node, block, None)
            if isinstance(children, list):
                self.walk(cast(list[ast.stmt], children), child_bindings, inherited_containers=containers)
        for handler in getattr(node, "handlers", ()):
            handler_bindings = dict(bindings)
            if handler.name:
                handler_bindings[handler.name] = ""
            self.walk(handler.body, handler_bindings, inherited_containers=containers)

    def _function_scope(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        bindings: dict[str, str],
        containers: dict[str, str],
        class_owner: str,
    ) -> None:
        local = dict(bindings)
        local_containers = dict(containers)
        arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
        for argument in arguments:
            local[argument.arg] = ""
            local_containers.pop(argument.arg, None)
            if argument.arg in {"self", "cls"} and class_owner:
                local[argument.arg] = class_owner
            if argument.annotation is not None:
                owner = self._expression(argument.annotation, bindings, containers)
                if owner:
                    local[argument.arg] = owner
                if self.receivers is not None:
                    item_type = iterable_receiver_type(
                        argument.annotation, self.module.name, bindings, self.receivers.classes
                    )
                    if item_type:
                        local_containers[argument.arg] = item_type
        self.walk(node.body, local, inherited_containers=local_containers)

    def _assignment_scope(
        self, node: ast.Assign | ast.AnnAssign, bindings: dict[str, str], containers: dict[str, str]
    ) -> None:
        value = node.value
        owner = self._assignment_owner(node, bindings, containers)
        item_type = self._element(value, bindings, containers) if value is not None else ""
        if isinstance(node, ast.AnnAssign) and self.receivers is not None:
            item_type = iterable_receiver_type(node.annotation, self.module.name, bindings, self.receivers.classes)
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        bind_targets(targets, owner, item_type, bindings, containers)

    def _assignment_owner(
        self, node: ast.Assign | ast.AnnAssign, bindings: dict[str, str], containers: dict[str, str]
    ) -> str:
        value = node.value
        owner = ""
        if isinstance(node, ast.AnnAssign):
            owner = self._expression(node.annotation, bindings, containers)
        if not owner and isinstance(value, ast.Call):
            owner = self._expression(value.func, bindings, containers)
            if self.receivers is not None:
                owner = self.receivers.returns.get(owner, owner)
        if not owner and isinstance(value, ast.Name | ast.Subscript):
            owner = self._expression(value, bindings, containers)
        return owner

    def _loop_scope(
        self, node: ast.For | ast.AsyncFor, bindings: dict[str, str], containers: dict[str, str]
    ) -> dict[str, str]:
        if self.whole_uses is not None:
            self.whole_uses.add(self._expression(node.iter, bindings, containers))
        child_bindings = dict(bindings)
        if isinstance(node.target, ast.Name):
            child_bindings.pop(node.target.id, None)
            item_type = self._element(node.iter, bindings, containers)
            if item_type:
                child_bindings[node.target.id] = item_type
        return child_bindings

    def _with_scope(self, node: ast.With | ast.AsyncWith, bindings: dict[str, str], containers: dict[str, str]) -> None:
        if self.receivers is None:
            return
        for item in node.items:
            if isinstance(item.context_expr, ast.Call) and isinstance(item.optional_vars, ast.Name):
                bindings.pop(item.optional_vars.id, None)
                owner = self.receivers.contexts.get(self._expression(item.context_expr.func, bindings, containers))
                if owner is not None and owner:
                    bindings[item.optional_vars.id] = owner

    def _visit_expression(self, part: ast.AST, scoped: dict[str, str], containers: dict[str, str]) -> None:
        if isinstance(part, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            self._comprehension(part, scoped, containers)
            return
        if isinstance(part, ast.Attribute):
            self._attribute_use(part, scoped, containers)
        elif self.calls is not None and isinstance(part, ast.Call):
            self._record_call(part, scoped, containers)

    def _record_call(self, part: ast.Call, scoped: dict[str, str], containers: dict[str, str]) -> None:
        if self.calls is None:
            return
        self.calls.append(
            ResolvedCall(
                self._expression(part.func, scoped, containers),
                tuple((keyword.arg, self._expression(keyword.value, scoped, containers)) for keyword in part.keywords),
                frozenset(
                    self._expression(item, scoped, containers)
                    for argument in part.args
                    for item in (argument, *ast.walk(argument))
                    if isinstance(item, ast.Name | ast.Attribute | ast.Call)
                ),
                tuple(self._expression(argument, scoped, containers) for argument in part.args),
            )
        )

    def _attribute_use(self, part: ast.Attribute, scoped: dict[str, str], containers: dict[str, str]) -> None:
        target = self._expression(part, scoped, containers)
        parts = target.split(".")
        for end in range(len(parts) - 2, 0, -1):
            owner = ".".join(parts[:end])
            if owner in self.known:
                self.uses.add((owner, ".".join(parts[end:])))
                break

    def _comprehension(
        self,
        part: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        scoped: dict[str, str],
        containers: dict[str, str],
    ) -> None:
        local = dict(scoped)
        for generator in part.generators:
            self._comprehension_generator(generator, local, containers)
        results = (part.key, part.value) if isinstance(part, ast.DictComp) else (part.elt,)
        for result in results:
            for inner in expression_nodes(result):
                self._visit_expression(inner, local, containers)

    def _comprehension_generator(
        self, generator: ast.comprehension, local: dict[str, str], containers: dict[str, str]
    ) -> None:
        if self.whole_uses is not None:
            self.whole_uses.add(self._expression(generator.iter, local, containers))
        for inner in expression_nodes(generator.iter):
            self._visit_expression(inner, local, containers)
        if isinstance(generator.target, ast.Name):
            item_type = self._element(generator.iter, local, containers)
            local.pop(generator.target.id, None)
            if item_type:
                local[generator.target.id] = item_type
        for condition in generator.ifs:
            for inner in expression_nodes(condition):
                self._visit_expression(inner, local, containers)
            self._narrow(condition, local)
