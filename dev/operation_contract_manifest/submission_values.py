"""Trace submission identity choices and payload constructors."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod

from cadrumo.entrypoints.tests.source_tree_support import SourceTree, module_level_bindings

from .submission_source import (
    NO_TRAIL,
    NOTHING,
    OPAQUE,
    Choice,
    ConstantToken,
    FlowValue,
    ModuleIndex,
    Resolution,
    Scope,
    Symbol,
    Trail,
)


class SubmissionValueFlow(ABC):
    """Resolve values using a source index supplied by the flow reader."""

    _tree: SourceTree
    _identities: dict[tuple[Symbol, int], FlowValue]
    _payloads: dict[tuple[Symbol, int], FlowValue]

    @abstractmethod
    def _index(self, path: str) -> ModuleIndex:
        """Read the indexed declarations for a source file."""

    @abstractmethod
    def _origin(self, path: str, name: str) -> Symbol | None:
        """Find the origin of a source name."""

    @abstractmethod
    def _class_named(self, scope: Scope, name: str) -> Symbol | None:
        """Find a class named in a scope."""

    @abstractmethod
    def _resolve(self, scope: Scope, node: ast.AST) -> Resolution:
        """Resolve a source expression to its targets."""

    @abstractmethod
    def _annotated_classes(self, path: str, annotation: ast.expr) -> frozenset[Symbol]:
        """Resolve class references in an annotation."""

    @abstractmethod
    def _module_scope(self, path: str) -> Scope:
        """Return a source module's scope."""

    def _constant_token(self, scope: Scope, expression: ast.expr) -> ConstantToken | None:
        """Reduce an expression to the constant it names, or to nothing when it names none."""
        if isinstance(expression, ast.Constant):
            return ("literal", repr(expression.value))
        if isinstance(expression, ast.Name) and not scope.binds(expression.id):
            origin = self._origin(scope.path, expression.id)
            binding = None if origin is None else self._index(origin[0]).bindings.get(origin[1])
            return ("literal", repr(binding.value)) if isinstance(binding, ast.Constant) else None
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            owner = self._class_named(scope, expression.value.id)
            if owner is None:
                return None
            return (*owner, self._member_spelling(owner, expression.attr))
        return None

    def _member_spelling(self, owner: Symbol, member: str) -> str:
        """Spell a class member by its value, so two names for one value read as the same constant."""
        definition = self._index(owner[0]).classes[owner[1]]
        for name, value in module_level_bindings(ast.Module(body=definition.body, type_ignores=[])):
            if name == member:
                return ast.dump(value)
        return member

    def _choice(self, scope: Scope, expression: ast.IfExp, trail: Trail) -> FlowValue | None:
        """Read ``a if parameter == CONSTANT else b`` as a choice on that parameter."""
        test = expression.test
        if not isinstance(test, ast.Compare) or len(test.ops) != 1:
            return None
        operator = test.ops[0]
        if not isinstance(operator, ast.Eq | ast.Is | ast.NotEq | ast.IsNot):
            return None
        for subject, constant in ((test.left, test.comparators[0]), (test.comparators[0], test.left)):
            if not isinstance(subject, ast.Name) or not scope.is_plain_parameter(subject.id):
                continue
            token = self._constant_token(scope, constant)
            if token is None:
                continue
            matching = self._read_identity(scope, expression.body, trail)
            otherwise = self._read_identity(scope, expression.orelse, trail)
            if isinstance(operator, ast.NotEq | ast.IsNot):
                matching, otherwise = otherwise, matching
            return FlowValue(choices=frozenset({Choice(subject.id, token, matching, otherwise)}))
        return None

    # -- the value of a definition id -------------------------------------

    def _identity(self, scope: Scope, expression: ast.expr) -> FlowValue:
        key = (scope.symbol, id(expression))
        value = self._identities.get(key)
        if value is None:
            value = self._read_identity(scope, expression, NO_TRAIL)
            self._identities[key] = value
        return value

    def _identity_choice(self, scope: Scope, expression: ast.IfExp, trail: Trail) -> FlowValue:
        choice = self._choice(scope, expression, trail)
        if choice is not None:
            return choice
        return self._read_identity(scope, expression.body, trail) | self._read_identity(scope, expression.orelse, trail)

    def _read_identity(self, scope: Scope, expression: ast.expr, trail: Trail) -> FlowValue:
        if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
            return FlowValue(constants=frozenset({expression.value}))
        if isinstance(expression, ast.IfExp):
            return self._identity_choice(scope, expression, trail)
        if isinstance(expression, ast.Name):
            return self._identity_of_name(scope, expression.id, trail)
        if isinstance(expression, ast.Subscript):
            selected = self._members(scope, expression.value, trail).settled()
            return FlowValue(members=selected.constants | selected.members, opaque=True)
        if isinstance(expression, ast.Attribute) and isinstance(expression.value, ast.Name):
            module = self._tree.module_aliases(scope.path).get(expression.value.id)
            if module is not None and not scope.binds(expression.value.id):
                return self._identity_of_binding((module, expression.attr), trail)
        return OPAQUE

    def _members(self, scope: Scope, container: ast.expr, trail: Trail) -> FlowValue:
        """Read the values a subscripted collection can yield, when its literal is in the source."""
        if isinstance(container, ast.Dict):
            values = list(container.values)
        elif isinstance(container, ast.Tuple | ast.List):
            values = list(container.elts)
        elif isinstance(container, ast.Name) and not scope.binds(container.id):
            origin = self._origin(scope.path, container.id)
            binding = None if origin is None else self._index(origin[0]).bindings.get(origin[1])
            if origin is None or binding is None or (origin, container.id) in trail:
                return NOTHING
            return self._members(self._module_scope(origin[0]), binding, trail | {(origin, container.id)})
        else:
            return NOTHING
        found = NOTHING
        for value in values:
            found |= self._read_identity(scope, value, trail)
        return found

    def _identity_of_name(self, scope: Scope, name: str, trail: Trail) -> FlowValue:
        if (scope.symbol, name) in trail:
            return NOTHING
        if not scope.binds(name):
            origin = self._origin(scope.path, name)
            return OPAQUE if origin is None else self._identity_of_binding(origin, trail)
        value = FlowValue(opaque=name in scope.rebound or name in scope.contexts)
        if name in scope.parameters:
            value |= FlowValue(parameters=frozenset({name}))
        for assigned in scope.assigned.get(name, ()):
            value |= self._read_identity(scope, assigned, trail | {(scope.symbol, name)})
        return value

    def _identity_of_binding(self, origin: Symbol, trail: Trail) -> FlowValue:
        binding = self._index(origin[0]).bindings.get(origin[1])
        if binding is None or (origin, origin[1]) in trail:
            return OPAQUE
        return self._read_identity(self._module_scope(origin[0]), binding, trail | {(origin, origin[1])})

    # -- the classes a payload is built from ------------------------------

    def _payload(self, scope: Scope, expression: ast.expr) -> FlowValue:
        key = (scope.symbol, id(expression))
        value = self._payloads.get(key)
        if value is None:
            value = self._read_payload(scope, expression, NO_TRAIL)
            self._payloads[key] = value
        return value

    def _read_payload(self, scope: Scope, expression: ast.expr, trail: Trail) -> FlowValue:
        """Name the classes an expression's object is built from.

        A constructed class is named and its arguments are left alone: they
        are its fields, not the object. A call that returns something else
        passes on what it was given, so encoding a request still reads as that
        request. Anything the reading cannot place makes the value opaque.
        """
        if isinstance(expression, ast.Await):
            return self._read_payload(scope, expression.value, trail)
        if isinstance(expression, ast.IfExp):
            return self._read_payload(scope, expression.body, trail) | self._read_payload(
                scope, expression.orelse, trail
            )
        if isinstance(expression, ast.Name):
            return self._payload_of_name(scope, expression.id, trail)
        if isinstance(expression, ast.Call):
            return self._payload_of_call(scope, expression, trail)
        return OPAQUE

    def _payload_of_name(self, scope: Scope, name: str, trail: Trail) -> FlowValue:
        if (scope.symbol, name) in trail:
            return NOTHING
        if not scope.binds(name):
            return OPAQUE
        value = FlowValue(opaque=name in scope.rebound or name in scope.contexts)
        if name in scope.parameters:
            value |= FlowValue(parameters=frozenset({name}))
        for assigned in scope.assigned.get(name, ()):
            value |= self._read_payload(scope, assigned, trail | {(scope.symbol, name)})
        return value

    def _call_returned_classes(self, scope: Scope, callee: ast.expr) -> set[Symbol]:
        returned: set[Symbol] = set()
        for target in self._resolve(scope, callee).targets:
            index = self._index(target[0])
            if target[1] in index.classes:
                returned.add(target)
                continue
            function = index.functions.get(target[1])
            if function is not None and function.returns is not None:
                returned.update(self._annotated_classes(target[0], function.returns))
        return returned

    def _qualified_constructor(self, scope: Scope, callee: ast.expr) -> FlowValue | None:
        if isinstance(callee, ast.Attribute) and isinstance(callee.value, ast.Name):
            owner = self._class_named(scope, callee.value.id)
            if owner is not None:
                return FlowValue(types=frozenset({owner}))
        return None

    def _payload_of_call(self, scope: Scope, call: ast.Call, trail: Trail) -> FlowValue:
        callee = call.func
        qualified = self._qualified_constructor(scope, callee)
        if qualified is not None:
            return qualified
        returned = self._call_returned_classes(scope, callee)
        if returned:
            return FlowValue(types=frozenset(returned))
        passed: list[ast.expr] = [*call.args, *(keyword.value for keyword in call.keywords)]
        if isinstance(callee, ast.Attribute):
            passed = [callee.value]
        if not passed or any(isinstance(argument, ast.Starred) for argument in passed):
            return OPAQUE
        value = NOTHING
        for argument in passed:
            value |= self._read_payload(scope, argument, trail)
        return value
