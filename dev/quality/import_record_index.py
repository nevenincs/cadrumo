"""Canonical records and resolver composition discovered from source."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from collections.abc import Mapping

from .import_check_models import SourceModule
from .import_module_syntax import qualified_name
from .import_record_annotations import annotation_classes
from .import_record_definitions import default_argument, field_names, index_definitions
from .import_record_models import SourceExpression
from .import_record_post_init import is_dataclass, normalizes_module
from .import_target_evaluation import TargetEvaluationContext


class DeclarationIndex(ABC):
    """Trace finite declaration index without executing product code."""

    def __init__(self, modules: Mapping[str, SourceModule]) -> None:
        """Index canonical definitions and their lexical contexts."""
        self.modules = modules
        self.contexts: dict[str, TargetEvaluationContext] = {}
        self.definitions, self.classes = index_definitions(modules)
        self._field_cache: dict[str, tuple[ast.AnnAssign, ...]] = {}
        self._closed_factory_classes: set[str] = set()
        self.callback_sources: dict[str, list[SourceExpression]] = {}
        self.target_fields = self._index_target_fields()
        self._index_graph_callbacks()
        self._index_direct_calls()

    def context(self, module: str) -> TargetEvaluationContext:
        """Build lexical indexes only for declarations reached by a projection."""
        if module not in self.contexts:
            self.contexts[module] = TargetEvaluationContext(self.modules[module].tree, module)
        return self.contexts[module]

    def reference(self, module: str, node: ast.AST) -> str | None:
        """Resolve a canonical definition through an explicit import binding."""
        name = qualified_name(node)
        if name is None:
            return None
        head, separator, tail = name.partition(".")
        binding = self.modules[module].bindings.get(head)
        if binding is not None and binding.target is not None:
            parts = [binding.target]
            if binding.imported_name is not None:
                parts.append(binding.imported_name)
            if separator:
                parts.append(tail)
            return ".".join(parts)
        return f"{module}.{name}"

    def fields(self, reference: str) -> tuple[ast.AnnAssign, ...]:
        """Return proved dataclass fields, caching within this one source inventory."""
        if reference not in self._field_cache:
            definition = self.classes.get(reference)
            self._field_cache[reference] = (
                tuple(
                    node
                    for node in definition.body
                    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                )
                if definition is not None and is_dataclass(reference, definition, self.reference)
                else ()
            )
        return self._field_cache[reference]

    def constructor_reference(self, expression: SourceExpression) -> str | None:
        """Resolve a factory's explicitly bound constructor, including ``cls``."""
        if not isinstance(expression.node, ast.Call):
            return None
        function = expression.node.func
        if isinstance(function, ast.Name) and function.id in expression.bindings:
            values = expression.bindings[function.id]
            if len(values) != 1:
                return None
            return self.reference(values[0].module, values[0].node)
        return self.reference(expression.module, function)

    def _argument(self, expression: SourceExpression, name: str) -> SourceExpression | None:
        node = expression.node
        if not isinstance(node, ast.Call):
            return None
        reference = self.constructor_reference(expression)
        names = field_names(self.fields(reference or ""))
        for keyword in node.keywords:
            if keyword.arg == name:
                return SourceExpression(expression.module, keyword.value, expression.bindings)
        if name in names and len(node.args) > names.index(name):
            return SourceExpression(expression.module, node.args[names.index(name)], expression.bindings)
        return default_argument(reference or "", name, self.fields(reference or ""))

    def _index_graph_callbacks(self) -> None:
        for module in self.modules.values():
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.Call):
                    continue
                self._index_graph(module, node)

    def _index_target_fields(self) -> frozenset[tuple[str, str]]:
        related: set[tuple[str, str]] = set()
        changed = True
        while changed:
            changed = False
            relevant_classes = {reference for reference, _ in related}
            for reference in self.classes:
                changed |= self._add_target_fields(reference, relevant_classes, related)
        return frozenset(related)

    def _add_target_fields(self, reference: str, relevant_classes: set[str], related: set[tuple[str, str]]) -> bool:
        fields = self.fields(reference)
        module = reference.rpartition(".")[0]
        names = {item.target.id for item in fields if isinstance(item.target, ast.Name)}
        changed = False
        for item in fields:
            if not isinstance(item.target, ast.Name):
                continue
            targets = annotation_classes(
                module, item.annotation, frozenset(), self.reference, self.classes, self.definitions
            )
            if "module" in names or targets & relevant_classes:
                key = (reference, item.target.id)
                if key not in related:
                    related.add(key)
                    changed = True
        return changed

    def normalizes_module(self, expression: SourceExpression) -> bool:
        """Recognize the proved standard relative-module normalization in post-init."""
        reference = self.constructor_reference(expression)
        definition = self.classes.get(reference or "")
        return definition is not None and normalizes_module(
            (reference or "").rpartition(".")[0], definition, self.reference
        )

    def _index_direct_calls(self) -> None:
        for module in self.modules.values():
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.Call):
                    continue
                self._index_call(module, node)

    def _index_call(self, module: SourceModule, node: ast.Call) -> None:
        callback = self.reference(module.name, node.func)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "resolver":
            self._index_resolver_call(module, node, node.func.value)
            return
        if callback not in self.callback_sources:
            return
        if node.args:
            source = node.args[0]
        else:
            definition = self.definitions.get(callback)
            if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)) or not definition.args.args:
                return
            name = definition.args.args[0].arg
            source = next((keyword.value for keyword in node.keywords if keyword.arg == name), None)
        if source is not None:
            self.callback_sources[callback].append(SourceExpression(module.name, source))

    def _index_resolver_call(self, module: SourceModule, node: ast.Call, receiver: ast.expr) -> None:
        try:
            graphs = self._expand(SourceExpression(module.name, receiver), (), frozenset())
        except (ValueError, RecursionError):
            graphs = ()
        for graph in graphs:
            resolver = self._argument(graph, "resolver")
            owner = self.reference(resolver.module, resolver.node) if resolver is not None else None
            if owner in self.callback_sources and node.args:
                self.callback_sources[owner].append(SourceExpression(module.name, node.args[0]))

    def _index_graph(self, module: SourceModule, node: ast.Call) -> None:
        reference = self.reference(module.name, node.func)
        fields = {item.target.id for item in self.fields(reference or "") if isinstance(item.target, ast.Name)}
        if not {"declared", "families", "resolver"} <= fields:
            return
        expression = SourceExpression(module.name, node)
        resolver = self._argument(expression, "resolver")
        callback = self.reference(resolver.module, resolver.node) if resolver is not None else None
        if callback is None:
            return
        sources = self.callback_sources.setdefault(callback, [])
        for name in ("declared", "families"):
            source = self._argument(expression, name)
            if source is not None:
                sources.append(source)

    @abstractmethod
    def _expand(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        """Expand finite declaration sources supplied by the concrete evaluator."""
        raise NotImplementedError
