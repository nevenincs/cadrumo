"""Bounded receiver provenance for dynamic imports."""

from __future__ import annotations

import ast

from .import_record_factory_safety import FactorySafetyProvenance
from .import_record_models import SourceExpression


class FactoryProvenance(FactorySafetyProvenance):
    """Prove factory receivers and their input closure."""

    def _bound_method_results(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...] | None:
        node = expression.node
        if not isinstance(node, ast.Call):
            return None
        function = node.func
        if isinstance(function, ast.Name):
            resolved = self._resolve_bound_name(expression.module, node, function)
            if resolved is None:
                return None
            function = resolved
        if not isinstance(function, ast.Attribute):
            return None
        if isinstance(function.value, ast.Name):
            _require_bound_receiver(function.value, expression)
        elif not self._known_receiver(expression.module, function.value):
            raise ValueError("unknown factory receiver construction")
        receivers = self._expand(SourceExpression(expression.module, function.value, expression.bindings), (), visiting)
        results: list[SourceExpression] = []
        for receiver in receivers:
            resolved = self._bound_receiver(expression, function, receiver, path, visiting)
            if resolved is None:
                return None
            results.extend(resolved)
        return tuple(results) if receivers else None

    def _known_receiver(self, module: str, value: ast.expr) -> bool:
        return isinstance(value, ast.Call) and self.reference(module, value.func) in self.classes

    def _resolve_bound_name(self, module: str, node: ast.Call, function: ast.Name) -> ast.AST | None:
        self._require_unescaped_factory_name(module, function.id)
        context = self.context(module)
        assignments = context.latest_values(function.id, getattr(node, "lineno", 10**9), context.nearest_function(node))
        return assignments[0].value if assignments is not None and len(assignments) == 1 else None

    def _bound_receiver(
        self,
        expression: SourceExpression,
        function: ast.Attribute,
        receiver: SourceExpression,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...] | None:
        owner = self.constructor_reference(receiver)
        if owner is None or not self.fields(owner):
            return None
        self._require_construction_only_class(owner)
        if f"{owner}.__post_init__" in self.definitions:
            raise ValueError("factory receiver has post-init behavior")
        for field in self.fields(owner):
            if not isinstance(field.target, ast.Name):
                continue
            argument = self._argument(receiver, field.target.id)
            if argument is None:
                raise ValueError("unknown factory constructor input")
            self._require_closed_factory_input(argument, frozenset())
        reference = f"{owner}.{function.attr}"
        definition = self.definitions.get(reference)
        if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return None
        return self._factory_results(expression, reference, definition, path, visiting, receiver=receiver)

    def _factory_results(
        self,
        expression: SourceExpression,
        reference: str,
        definition: ast.FunctionDef | ast.AsyncFunctionDef,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
        *,
        receiver: SourceExpression | None = None,
    ) -> tuple[SourceExpression, ...]:
        call = expression.node
        if not isinstance(call, ast.Call):
            raise ValueError("expected factory call")
        module, owner, bindings = self._factory_bindings(expression, reference, definition, call, receiver)
        rebound = _rebound_names(definition)
        if rebound & bindings.keys():
            raise ValueError("factory parameter is rebound")
        if receiver is not None:
            self._require_pure_receiver_method(owner, definition, frozenset())
        returns = self._factory_returns(module, definition)
        if not returns:
            return self._walked_records(module, reference, definition, bindings, path, visiting)
        return tuple(
            item
            for result in returns
            if result.value is not None
            for item in self._expand(SourceExpression(module, result.value, bindings), path, visiting)
        )

    def _factory_returns(self, module: str, definition: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Return]:
        returns = [
            node
            for node in ast.walk(definition)
            if isinstance(node, ast.Return)
            and node.value is not None
            and self.context(module).nearest_function(node) is definition
        ]
        return returns

    def _factory_bindings(
        self,
        expression: SourceExpression,
        reference: str,
        definition: ast.FunctionDef | ast.AsyncFunctionDef,
        call: ast.Call,
        receiver: SourceExpression | None,
    ) -> tuple[str, str, dict[str, tuple[SourceExpression, ...]]]:
        parameters = (*definition.args.posonlyargs, *definition.args.args)
        bindings: dict[str, tuple[SourceExpression, ...]] = {}
        owner, _, _ = reference.rpartition(".")
        module = owner
        if owner in self.classes:
            module = owner.rpartition(".")[0]
            if parameters and parameters[0].arg == "self":
                if receiver is None:
                    raise ValueError("unknown factory receiver")
                bindings["self"] = (receiver,)
                parameters = parameters[1:]
            if parameters and parameters[0].arg == "cls":
                bindings["cls"] = (SourceExpression(module, ast.Name(id=owner.rpartition(".")[2])),)
                parameters = parameters[1:]
        for parameter, value in zip(parameters, call.args, strict=False):
            bindings[parameter.arg] = (SourceExpression(expression.module, value, expression.bindings),)
        for keyword in call.keywords:
            if keyword.arg is None:
                raise ValueError("open keyword arguments")
            bindings[keyword.arg] = (SourceExpression(expression.module, keyword.value, expression.bindings),)
        _default_bindings(definition, module, bindings)
        return module, owner, bindings


def _rebound_names(definition: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {
        target.id
        for item in ast.walk(definition)
        if isinstance(item, (ast.Assign, ast.AnnAssign, ast.NamedExpr, ast.AugAssign))
        for target in ast.walk(item)
        if isinstance(target, ast.Name) and isinstance(target.ctx, ast.Store)
    }


def _default_bindings(
    definition: ast.FunctionDef | ast.AsyncFunctionDef, module: str, bindings: dict[str, tuple[SourceExpression, ...]]
) -> None:
    for parameter, default in zip(
        definition.args.args[-len(definition.args.defaults) :] if definition.args.defaults else (),
        definition.args.defaults,
        strict=True,
    ):
        bindings.setdefault(parameter.arg, (SourceExpression(module, default),))
    for parameter, default in zip(definition.args.kwonlyargs, definition.args.kw_defaults, strict=True):
        if default is not None:
            bindings.setdefault(parameter.arg, (SourceExpression(module, default),))


def _require_bound_receiver(name: ast.Name, expression: SourceExpression) -> None:
    if name.id not in expression.bindings:
        raise ValueError("named mutable factory receiver")
