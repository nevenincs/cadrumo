"""Bounded receiver provenance for dynamic imports."""

from __future__ import annotations

import ast
from typing import override

from .import_record_definitions import field_names
from .import_record_graphs import RecordGraphProvenance
from .import_record_models import SourceExpression
from .import_record_projection import iteration_projection


class RecordTargetProvenance(RecordGraphProvenance):
    """Trace finite declaration recordtargetprovenance without executing product code."""

    def targets(self, module: str, node: ast.AST) -> frozenset[str] | None:
        """Resolve only values reaching this receiver; open branches fail closed."""
        try:
            expressions = self._expand(SourceExpression(module, node), (), frozenset())
            targets: set[str] = set()
            for expression in expressions:
                values = self._strings(expression)
                if values is None:
                    return None
                targets.update(values)
            return frozenset(targets) if targets else None
        except (RecursionError, ValueError):
            return None

    @override
    def _expand(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if expression.wrapped_node and path:
            return self._expand_wrapped(expression, path, visiting)
        key = (expression.module, id(node), path)
        if key in visiting or len(visiting) > 80:
            raise ValueError("cyclic or unbounded declaration source")
        visiting = visiting | {key}
        if isinstance(node, ast.Attribute):
            return self._expand(
                SourceExpression(expression.module, node.value, expression.bindings), (node.attr, *path), visiting
            )
        if isinstance(node, ast.Name):
            return self._expand_name(expression, path, visiting)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return self._expand_many(expression, node.elts, path, visiting)
        if isinstance(node, ast.DictComp):
            return self._expand_dict_comprehension(expression, node, path, visiting)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            return self._expand_comprehension(expression, node, path, visiting)
        return self._expand_remaining(expression, path, visiting)

    def _expand_wrapped(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        if path[0] != "spec":
            raise ValueError("unknown command-node projection")
        return self._expand(
            SourceExpression(expression.module, expression.node, expression.bindings), path[1:], visiting
        )

    def _expand_many(
        self,
        expression: SourceExpression,
        values: list[ast.expr],
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        return tuple(
            item
            for value in values
            for item in self._expand(SourceExpression(expression.module, value, expression.bindings), path, visiting)
        )

    def _expand_remaining(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if isinstance(node, ast.BoolOp):
            return self._expand_many(expression, node.values, path, visiting)
        if isinstance(node, (ast.Starred, ast.Subscript)):
            return self._expand(SourceExpression(expression.module, node.value, expression.bindings), path, visiting)
        if isinstance(node, ast.IfExp):
            return self._expand_conditional(expression, node, path, visiting)
        if isinstance(node, ast.Call):
            return self._expand_call(expression, path, visiting)
        if isinstance(node, ast.Constant) and node.value is None:
            return ()
        if path:
            raise ValueError("unresolved record projection")
        return (expression,)

    def _expand_dict_comprehension(
        self,
        expression: SourceExpression,
        node: ast.DictComp,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        bindings = dict(expression.bindings)
        for generator in node.generators:
            if isinstance(generator.target, ast.Name):
                bindings[generator.target.id] = (SourceExpression(expression.module, generator.iter, dict(bindings)),)
            elif isinstance(generator.target, ast.Tuple):
                for index, target in enumerate(generator.target.elts):
                    if not isinstance(target, ast.Name):
                        raise ValueError("unsupported mapping generator")
                    if index == 1:
                        bindings[target.id] = (
                            iteration_projection(
                                SourceExpression(expression.module, generator.iter, dict(bindings)), (index,)
                            ),
                        )
            else:
                raise ValueError("unsupported mapping generator")
        return self._expand(SourceExpression(expression.module, node.value, bindings), path, visiting)

    def _expand_comprehension(
        self,
        expression: SourceExpression,
        node: ast.ListComp | ast.SetComp | ast.GeneratorExp,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        bindings = dict(expression.bindings)
        for generator in node.generators:
            if not isinstance(generator.target, ast.Name):
                raise ValueError("unsupported comprehension binding")
            values = self._expand(SourceExpression(expression.module, generator.iter, bindings), (), visiting)
            bindings[generator.target.id] = values
        return self._expand(SourceExpression(expression.module, node.elt, bindings), path, visiting)

    def _expand_conditional(
        self,
        expression: SourceExpression,
        node: ast.IfExp,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        if (
            isinstance(node.test, ast.Call)
            and isinstance(node.test.func, ast.Name)
            and node.test.func.id == "isinstance"
        ):
            branch = self._record_type_branch(expression)
            return self._expand(SourceExpression(expression.module, branch, expression.bindings), path, visiting)
        return tuple(
            item
            for branch in (node.body, node.orelse)
            for item in self._expand(SourceExpression(expression.module, branch, expression.bindings), path, visiting)
        )

    @override
    def _callback_targets(self, callback: str) -> frozenset[str]:
        targets: set[str] = set()
        for source in self.callback_sources[callback]:
            targets.update(self._collect_targets(source, frozenset()))
        if not targets or len(targets) > 4096:
            raise ValueError("empty or unbounded callback source")
        return frozenset(targets)

    def _collect_targets(self, source: SourceExpression, visiting: frozenset[tuple[str, int]]) -> frozenset[str]:
        key = (source.module, id(source.node))
        if key in visiting or len(visiting) > 80:
            raise ValueError("cyclic declaration inventory")
        visiting = visiting | {key}
        targets: set[str] = set()
        for expression in self._expand(source, (), frozenset()):
            self._collect_record(expression, visiting, targets)
        return frozenset(targets)

    def _collect_record(
        self, expression: SourceExpression, visiting: frozenset[tuple[str, int]], targets: set[str]
    ) -> None:
        if not _record_call(expression):
            return
        reference = self.constructor_reference(expression)
        names = set(field_names(self.fields(reference or "")))
        if "module" in names:
            targets.update(self._record_modules(expression))
            return
        for name in names:
            if (reference or "", name) not in self.target_fields:
                continue
            child = self._argument(expression, name)
            if child is None:
                raise ValueError("missing declaration field")
            targets.update(self._collect_targets(child, visiting))
        if {"mount_key", "source"} <= names:
            self._collect_family(expression, visiting, targets)

    def _collect_family(
        self, expression: SourceExpression, visiting: frozenset[tuple[str, int]], targets: set[str]
    ) -> None:
        child = self._argument(expression, "source")
        if child is None:
            raise ValueError("unknown family declaration")
        for record in self._expand(child, (), frozenset()):
            modules = self._record_modules(record)
            qualname = self._argument(record, "qualname")
            qualnames = self._strings(qualname) if qualname is not None else None
            if qualnames is None:
                raise ValueError("unknown family symbol")
            for module in modules:
                if module not in self.modules:
                    raise ValueError("unknown family module")
                for symbol in qualnames:
                    targets.update(self._collect_targets(self._module_assignment(module, symbol), visiting))


def _record_call(expression: SourceExpression) -> bool:
    node = expression.node
    if isinstance(node, ast.Call):
        return True
    if isinstance(node, ast.Constant) and node.value is None:
        return False
    raise ValueError(
        f"unknown declaration record: {expression.module}:{getattr(node, 'lineno', 0)} {ast.unparse(node)}"
    )
