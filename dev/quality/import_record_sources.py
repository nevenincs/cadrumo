"""Bounded receiver provenance for dynamic imports."""

from __future__ import annotations

import ast
from abc import abstractmethod

from .import_record_models import SourceExpression
from .import_record_projection import iteration_projection
from .import_record_source_parameters import ParameterSourceProvenance
from .import_target_evaluation import TargetAssignment


class RecordSourceProvenance(ParameterSourceProvenance):
    """Resolve scoped declaration and parameter sources."""

    def _expand_name(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if not isinstance(node, ast.Name):
            raise ValueError("expected name")
        if node.id in expression.bindings:
            return tuple(item for value in expression.bindings[node.id] for item in self._expand(value, path, visiting))
        context = self.context(expression.module)
        scope = context.nearest_function(node)
        assignments = context.latest_values(node.id, node.lineno, scope)
        if assignments is not None and assignments:
            return self._expand_assignments(expression, assignments, path, visiting)
        resolved = self._imported_or_callback(expression, node, scope, path, visiting)
        if resolved is not None:
            return resolved
        return self._expand_unbound_name(expression, node, scope, path, visiting)

    def _expand_unbound_name(
        self,
        expression: SourceExpression,
        node: ast.Name,
        scope: ast.AST | None,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        sources = self._comprehension_sources(expression)
        if sources is not None:
            return tuple(item for source in sources for item in self._expand(source, path, visiting))
        sources = self._function_parameter_source(expression.module, node, scope)
        if sources:
            return tuple(item for source in sources for item in self._expand(source, path, visiting))
        if not path:
            return (expression,)
        raise ValueError("unknown receiver source")

    def _function_parameter_source(
        self, module: str, node: ast.Name, scope: ast.AST | None
    ) -> tuple[SourceExpression, ...]:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.id in _parameter_names(scope):
            return self._parameter_sources(module, scope, node.id)
        return ()

    def _imported_or_callback(
        self,
        expression: SourceExpression,
        node: ast.Name,
        scope: ast.AST | None,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...] | None:
        parameters = _parameter_names(scope)
        binding = self.modules[expression.module].bindings.get(node.id) if node.id not in parameters else None
        if (
            binding is not None
            and binding.target is not None
            and binding.target in self.modules
            and binding.imported_name is not None
        ):
            imported = self._module_assignment(binding.target, binding.imported_name)
            return self._expand(imported, path, visiting)
        return self._callback_source(expression, node, scope, path)

    def _callback_source(
        self, expression: SourceExpression, node: ast.Name, scope: ast.AST | None, path: tuple[str, ...]
    ) -> tuple[SourceExpression, ...] | None:
        if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
            callback = f"{expression.module}.{scope.name}"
            positional_parameters = (*scope.args.posonlyargs, *scope.args.args)
            if positional_parameters and node.id == positional_parameters[0].arg and callback in self.callback_sources:
                targets = self._callback_targets(callback)
                if path != ("module",):
                    raise ValueError("unsupported callback projection")
                return tuple(SourceExpression(expression.module, ast.Constant(value=value)) for value in targets)
        return None

    def _expand_assignments(
        self,
        expression: SourceExpression,
        assignments: tuple[TargetAssignment, ...],
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        if any(assignment.projection for assignment in assignments):
            values: list[SourceExpression] = []
            for assignment in assignments:
                source = SourceExpression(expression.module, assignment.value, expression.bindings)
                if assignment.projection:
                    source = iteration_projection(source, assignment.projection)
                values.extend(self._expand(source, path, visiting))
            return tuple(values)
        return tuple(
            item
            for assignment in assignments
            for item in self._expand(
                SourceExpression(expression.module, assignment.value, expression.bindings), path, visiting
            )
        )

    def _comprehension_sources(self, expression: SourceExpression) -> tuple[SourceExpression, ...] | None:
        node = expression.node
        if not isinstance(node, ast.Name):
            return None
        context = self.context(expression.module)
        for candidate in ast.walk(self.modules[expression.module].tree):
            if not isinstance(candidate, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                continue
            visible = _visible_generators(candidate, node)
            if visible is None:
                continue
            if context.nearest_function(candidate) is not context.nearest_function(node):
                continue
            bindings = dict(expression.bindings)
            for generator in visible:
                if not isinstance(generator.target, ast.Name):
                    raise ValueError("unsupported comprehension source")
                bindings[generator.target.id] = (SourceExpression(expression.module, generator.iter, dict(bindings)),)
            return bindings.get(node.id)
        return None

    @abstractmethod
    def _callback_targets(self, callback: str) -> frozenset[str]:
        """Resolve the finite declarations supplied to a callback."""
        raise NotImplementedError


def _parameter_names(scope: ast.AST | None) -> set[str]:
    if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return set()
    return {item.arg for item in (*scope.args.posonlyargs, *scope.args.args, *scope.args.kwonlyargs)}


def _visible_generators(
    candidate: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp, node: ast.Name
) -> list[ast.comprehension] | None:
    projections = (candidate.key, candidate.value) if isinstance(candidate, ast.DictComp) else (candidate.elt,)
    visible = candidate.generators
    for index, generator in enumerate(candidate.generators):
        if any(any(item is node for item in ast.walk(condition)) for condition in generator.ifs):
            projections = tuple(generator.ifs)
            visible = candidate.generators[: index + 1]
            break
    return visible if any(any(item is node for item in ast.walk(projection)) for projection in projections) else None
