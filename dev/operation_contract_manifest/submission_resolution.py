"""Index and resolve source names, methods, and submission facts."""

from __future__ import annotations

import ast
from typing import override

from .submission_facts import SubmissionFactsFlow
from .submission_source import (
    RECEIVER_NAMES,
    UNRELATED,
    UNTRACED,
    ModuleIndex,
    Resolution,
    Scope,
    Symbol,
    is_member,
    runs_a_coroutine,
)


class SubmissionResolutionFlow(SubmissionFactsFlow):
    """Resolve callable relationships and receiver classes."""

    def _resolve_name(self, scope: Scope, node: ast.Name) -> Resolution:
        if not isinstance(node.ctx, ast.Load) or scope.binds(node.id):
            return UNRELATED
        origin = self._origin(scope.path, node.id)
        return UNRELATED if origin is None else Resolution(targets=(origin,))

    def _resolve_named_receiver(self, scope: Scope, receiver: ast.Name, member: str) -> Resolution:
        if receiver.id in RECEIVER_NAMES and scope.owner is not None:
            return self._methods((scope.owner,), member)
        if scope.binds(receiver.id):
            classes = self._classes_of_name(scope, receiver.id)
            return self._methods(tuple(sorted(classes)), member) if classes else UNTRACED
        module = self._tree.module_aliases(scope.path).get(receiver.id)
        if module is not None:
            return Resolution(targets=((module, member),)) if self._index(module).defines(member) else UNRELATED
        origin = self._class_named(scope, receiver.id)
        method = None if origin is None else self._method(origin, member)
        if method is None:
            return UNRELATED
        return Resolution(targets=(method,), bound=self._is_class_method(method))

    @override
    def _resolve(self, scope: Scope, node: ast.AST) -> Resolution:
        """Resolve a name or attribute to the symbols it can refer to."""
        if isinstance(node, ast.Name):
            return self._resolve_name(scope, node)
        if not isinstance(node, ast.Attribute) or not isinstance(node.ctx, ast.Load):
            return UNRELATED
        receiver = node.value
        if isinstance(receiver, ast.Attribute):
            return self._resolve_member_method(scope, receiver, node.attr)
        if isinstance(receiver, ast.Call):
            classes = self._classes_of_expression(scope, receiver)
            targets = tuple(
                self._callable_members[(cls, node.attr)]
                for cls in sorted(classes)
                if (cls, node.attr) in self._callable_members
            )
            if targets:
                return Resolution(targets=targets)
            return UNTRACED
        if not isinstance(receiver, ast.Name):
            return UNTRACED
        return self._resolve_named_receiver(scope, receiver, node.attr)

    def _resolve_member_method(self, scope: Scope, receiver: ast.Attribute, name: str) -> Resolution:
        """Resolve ``self.member.name`` through the class the member is declared or assigned as."""
        holder = receiver.value
        if not isinstance(holder, ast.Name) or holder.id not in RECEIVER_NAMES or scope.owner is None:
            return UNTRACED
        classes = self._classes_of_member(scope.owner, receiver.attr)
        return self._methods(tuple(sorted(classes)), name) if classes else UNTRACED

    def _methods(self, classes: tuple[Symbol, ...], name: str) -> Resolution:
        methods = (self._method(cls, name) for cls in classes)
        return Resolution(targets=tuple(method for method in methods if method is not None), bound=True)

    def _method(self, cls: Symbol, name: str) -> Symbol | None:
        """Find a method on a class or the nearest base that defines it."""
        pending = [cls]
        seen: set[Symbol] = set()
        while pending:
            current = pending.pop(0)
            if current in seen:
                continue
            seen.add(current)
            if f"{current[1]}.{name}" in self._index(current[0]).functions:
                return (current[0], f"{current[1]}.{name}")
            pending.extend(self._bases(current))
        return None

    def _is_class_method(self, method: Symbol) -> bool:
        function = self._index(method[0]).functions[method[1]]
        return any(isinstance(item, ast.Name) and item.id == "classmethod" for item in function.decorator_list)

    # -- the class of a receiver ------------------------------------------

    def _classes_of_name(self, scope: Scope, name: str) -> frozenset[Symbol]:
        key = (scope.symbol, name)
        known = self._receiver_classes.get(key)
        if known is None:
            # A name assigned from a call on itself would otherwise ask for its own class forever.
            self._receiver_classes[key] = frozenset()
            known = self._read_classes_of_name(scope, name)
            self._receiver_classes[key] = known
        return known

    def _read_classes_of_name(self, scope: Scope, name: str) -> frozenset[Symbol]:
        classes: set[Symbol] = set()
        parameter = scope.parameters.get(name)
        if parameter is not None and parameter.annotation is not None:
            classes.update(self._annotated_classes(scope.path, parameter.annotation))
        for source in (*scope.assigned.get(name, ()), *scope.contexts.get(name, ())):
            classes.update(self._classes_of_expression(scope, source))
        return frozenset(classes)

    def _member_method_classes(self, path: str, name: str, member: str, index: ModuleIndex) -> set[Symbol]:
        classes: set[Symbol] = set()
        for qualified, function in index.functions.items():
            if qualified.rpartition(".")[0] != name:
                continue
            method_scope = self._scope((path, qualified))
            for node in ast.walk(function):
                if isinstance(node, ast.AnnAssign) and is_member(node.target, member):
                    classes.update(self._annotated_classes(path, node.annotation))
                elif isinstance(node, ast.Assign) and any(is_member(target, member) for target in node.targets):
                    classes.update(self._classes_of_expression(method_scope, node.value))
        return classes

    def _classes_of_member(self, owner: Symbol, member: str) -> frozenset[Symbol]:
        """Name the classes an instance attribute holds, from its declaration and from what is assigned to it."""
        key = (owner, member)
        known = self._member_classes.get(key)
        if known is not None:
            return known
        self._member_classes[key] = frozenset()
        path, name = owner
        index = self._index(path)
        classes: set[Symbol] = set()
        definition = index.classes.get(name)
        for node in () if definition is None else definition.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == member:
                classes.update(self._annotated_classes(path, node.annotation))
        classes.update(self._member_method_classes(path, name, member, index))
        known = frozenset(classes)
        self._member_classes[key] = known
        return known

    def _classes_of_expression(self, scope: Scope, expression: ast.expr) -> frozenset[Symbol]:
        if isinstance(expression, ast.Await):
            expression = expression.value
        elif runs_a_coroutine(expression):
            # ``asyncio.run`` returns what the coroutine it is handed returns, as ``await`` does.
            expression = expression.args[0]
        if isinstance(expression, ast.Name) and scope.binds(expression.id):
            return self._classes_of_name(scope, expression.id)
        if not isinstance(expression, ast.Call):
            return frozenset[Symbol]()
        classes: set[Symbol] = set()
        for target in self._resolve(scope, expression.func).targets:
            index = self._index(target[0])
            if target[1] in index.classes:
                classes.add(target)
                continue
            function = index.functions.get(target[1])
            if function is not None and function.returns is not None:
                classes.update(self._annotated_classes(target[0], function.returns))
        return frozenset(classes)

    @override
    def _annotated_classes(self, path: str, annotation: ast.expr) -> frozenset[Symbol]:
        """Every class of the tree an annotation names, however it wraps them."""
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode="eval").body
            except SyntaxError:
                return frozenset[Symbol]()
        classes: set[Symbol] = set()
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name):
                origin = self._origin(path, node.id)
                if origin is not None and origin[1] in self._index(origin[0]).classes:
                    classes.add(origin)
        return frozenset(classes)

    # -- constants a choice can turn on -----------------------------------
