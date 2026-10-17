"""Canonical records and resolver composition discovered from source."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from collections.abc import Mapping

from .import_check_models import SourceModule
from .import_module_syntax import qualified_name
from .import_record_models import SourceExpression
from .import_target_evaluation import TargetEvaluationContext


class DeclarationIndex(ABC):
    """Trace finite declaration index without executing product code."""

    def __init__(self, modules: Mapping[str, SourceModule]) -> None:
        """Index canonical definitions and their lexical contexts."""
        self.modules = modules
        self.contexts: dict[str, TargetEvaluationContext] = {}
        self.definitions: dict[str, ast.AST] = {}
        self.classes: dict[str, ast.ClassDef] = {}
        self._field_cache: dict[str, tuple[ast.AnnAssign, ...]] = {}
        self.callback_sources: dict[str, list[SourceExpression]] = {}
        self._index_definitions()
        self.target_fields = self._index_target_fields()
        self._index_graph_callbacks()
        self._index_direct_calls()

    def context(self, module: str) -> TargetEvaluationContext:
        """Build lexical indexes only for declarations reached by a projection."""
        if module not in self.contexts:
            self.contexts[module] = TargetEvaluationContext(self.modules[module].tree, module)
        return self.contexts[module]

    def _index_definitions(self) -> None:
        for module in self.modules.values():
            for node in module.tree.body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.definitions[f"{module.name}.{node.name}"] = node
                if isinstance(node, ast.TypeAlias):
                    self.definitions[f"{module.name}.{node.name.id}"] = node
                if isinstance(node, ast.ClassDef):
                    self.classes[f"{module.name}.{node.name}"] = node
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            self.definitions[f"{module.name}.{node.name}.{child.name}"] = child

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
                if definition is not None and self._is_dataclass(reference, definition)
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
        names = [item.target.id for item in self.fields(reference or "") if isinstance(item.target, ast.Name)]
        for keyword in node.keywords:
            if keyword.arg == name:
                return SourceExpression(expression.module, keyword.value, expression.bindings)
        if name in names and len(node.args) > names.index(name):
            return SourceExpression(expression.module, node.args[names.index(name)], expression.bindings)
        for item in self.fields(reference or ""):
            if isinstance(item.target, ast.Name) and item.target.id == name and item.value is not None:
                return SourceExpression((reference or "").rpartition(".")[0], item.value)
        return None

    def _index_graph_callbacks(self) -> None:
        for module in self.modules.values():
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.Call):
                    continue
                reference = self.reference(module.name, node.func)
                fields = {item.target.id for item in self.fields(reference or "") if isinstance(item.target, ast.Name)}
                if not {"declared", "families", "resolver"} <= fields:
                    continue
                expression = SourceExpression(module.name, node)
                resolver = self._argument(expression, "resolver")
                callback = self.reference(resolver.module, resolver.node) if resolver is not None else None
                if callback is None:
                    continue
                sources = self.callback_sources.setdefault(callback, [])
                for name in ("declared", "families"):
                    source = self._argument(expression, name)
                    if source is not None:
                        sources.append(source)

    def _index_target_fields(self) -> frozenset[tuple[str, str]]:
        related: set[tuple[str, str]] = set()
        changed = True
        while changed:
            changed = False
            relevant_classes = {reference for reference, _ in related}
            for reference in self.classes:
                fields = self.fields(reference)
                module = reference.rpartition(".")[0]
                names = {item.target.id for item in fields if isinstance(item.target, ast.Name)}
                for item in fields:
                    if not isinstance(item.target, ast.Name):
                        continue
                    targets = self._annotation_classes(module, item.annotation, frozenset())
                    if "module" in names or targets & relevant_classes:
                        key = (reference, item.target.id)
                        if key not in related:
                            related.add(key)
                            changed = True
        return frozenset(related)

    def _annotation_classes(self, module: str, annotation: ast.AST, visiting: frozenset[str]) -> set[str]:
        targets: set[str] = set()
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                annotation = ast.parse(annotation.value, mode="eval")
            except SyntaxError:
                return targets
        for node in ast.walk(annotation):
            if not isinstance(node, (ast.Name, ast.Attribute)):
                continue
            reference = self.reference(module, node)
            if reference is None or reference in visiting:
                continue
            if reference in self.classes:
                targets.add(reference)
            alias = self.definitions.get(reference)
            if isinstance(alias, ast.TypeAlias):
                targets.update(
                    self._annotation_classes(reference.rpartition(".")[0], alias.value, visiting | {reference})
                )
        return targets

    def _is_dataclass(self, reference: str, definition: ast.ClassDef) -> bool:
        module = reference.rpartition(".")[0]
        if (
            definition.bases
            or definition.keywords
            or any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in {"__init__", "__new__", "__getattribute__", "__getattr__", "__setattr__"}
                for node in definition.body
            )
        ):
            return False
        if len(definition.decorator_list) != 1:
            return False
        decorator = definition.decorator_list[0]
        if (
            self.reference(module, decorator.func if isinstance(decorator, ast.Call) else decorator)
            != "dataclasses.dataclass"
        ):
            return False
        if isinstance(decorator, ast.Call) and any(
            keyword.arg == "init" and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is True)
            for keyword in decorator.keywords
        ):
            return False
        return self._post_init_is_closed(module, definition)

    def _post_init_is_closed(self, module: str, definition: ast.ClassDef) -> bool:
        for method in definition.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)) or method.name != "__post_init__":
                continue
            for node in ast.walk(method):
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
                    return False
                if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                    return False
                if not isinstance(node, ast.Call):
                    continue
                if any(isinstance(child, ast.Name) and child.id == "self" for child in ast.walk(node.func)) and not (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "startswith"
                    and qualified_name(node.func.value) == "self.module"
                    and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                    and not node.keywords
                ):
                    return False
                if not any(isinstance(argument, ast.Name) and argument.id == "self" for argument in node.args):
                    continue
                if qualified_name(node.func) != "object.__setattr__" or len(node.args) != 3:
                    return False
                field, value = node.args[1:]
                if not isinstance(field, ast.Constant) or field.value not in {"module", "package"}:
                    return False
                if field.value == "package" and isinstance(value, ast.Constant) and value.value is None:
                    continue
                if (
                    not isinstance(value, ast.Call)
                    or self.reference(module, value.func) != "importlib.util.resolve_name"
                ):
                    return False
                if [qualified_name(argument) for argument in value.args] != [
                    "self.module",
                    "self.package",
                ] or value.keywords:
                    return False
        return True

    def normalizes_module(self, expression: SourceExpression) -> bool:
        """Recognize the proved standard relative-module normalization in post-init."""
        reference = self.constructor_reference(expression)
        definition = self.classes.get(reference or "")
        if definition is None:
            return False
        module = (reference or "").rpartition(".")[0]
        return any(
            isinstance(node, ast.Call)
            and qualified_name(node.func) == "object.__setattr__"
            and len(node.args) == 3
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "module"
            and isinstance(node.args[2], ast.Call)
            and self.reference(module, node.args[2].func) == "importlib.util.resolve_name"
            and [qualified_name(argument) for argument in node.args[2].args] == ["self.module", "self.package"]
            for method in definition.body
            if isinstance(method, ast.FunctionDef) and method.name == "__post_init__"
            for node in ast.walk(method)
        )

    def _index_direct_calls(self) -> None:
        for module in self.modules.values():
            for node in ast.walk(module.tree):
                if not isinstance(node, ast.Call):
                    continue
                callback = self.reference(module.name, node.func)
                if isinstance(node.func, ast.Attribute) and node.func.attr == "resolver":
                    try:
                        graphs = self._expand(SourceExpression(module.name, node.func.value), (), frozenset())
                    except (ValueError, RecursionError):
                        graphs = ()
                    for graph in graphs:
                        resolver = self._argument(graph, "resolver")
                        owner = self.reference(resolver.module, resolver.node) if resolver is not None else None
                        if owner in self.callback_sources and node.args:
                            self.callback_sources[owner].append(SourceExpression(module.name, node.args[0]))
                    continue
                if callback not in self.callback_sources:
                    continue
                if node.args:
                    source = node.args[0]
                else:
                    definition = self.definitions.get(callback)
                    if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)) or not definition.args.args:
                        continue
                    name = definition.args.args[0].arg
                    source = next((keyword.value for keyword in node.keywords if keyword.arg == name), None)
                if source is not None:
                    self.callback_sources[callback].append(SourceExpression(module.name, source))

    @abstractmethod
    def _expand(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        """Expand finite declaration sources supplied by the concrete evaluator."""
        raise NotImplementedError
