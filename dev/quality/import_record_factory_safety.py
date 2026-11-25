"""Bounded receiver provenance for dynamic imports."""

from __future__ import annotations

import ast

from .import_record_models import SourceExpression
from .import_record_projection import reference_visible
from .import_record_purity import (
    contains_receiver_value,
    loaded_name,
    pure_record_classmethod,
    pure_return_statement,
    reference_node,
    require_constructor_use,
    require_unescaped_use,
)
from .import_record_walks import DeclarationWalks


class FactorySafetyProvenance(DeclarationWalks):
    """Prove factory construction and receiver purity."""

    def _require_construction_only_class(self, owner: str) -> None:
        if owner in self._closed_factory_classes:
            return
        for module, source in self.modules.items():
            if not reference_visible(self.modules, module, owner):
                continue
            parents = {id(child): parent for parent in ast.walk(source.tree) for child in ast.iter_child_nodes(parent)}
            for node in ast.walk(source.tree):
                if not reference_node(node) or self.reference(module, node) != owner:
                    continue
                parent = parents.get(id(node))
                require_constructor_use(parent, node)
        self._closed_factory_classes.add(owner)

    def _require_closed_factory_input(self, expression: SourceExpression, visiting: frozenset[tuple[str, int]]) -> None:
        node = expression.node
        key = (expression.module, id(node))
        if key in visiting or len(visiting) > 80:
            raise ValueError("cyclic factory input")
        visiting = visiting | {key}
        if isinstance(node, ast.Constant) or (isinstance(node, ast.Name) and node.id == "__package__"):
            return
        if isinstance(node, ast.Name):
            self._require_named_input(expression, node, visiting)
            return
        if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict)):
            self._require_container_input(expression, node, visiting)
            return
        if isinstance(node, ast.Attribute):
            self._require_enum_input(expression, node)
            return
        if isinstance(node, ast.Call):
            self._require_nested_input(expression, visiting)
            return
        raise ValueError("open factory input")

    def _require_named_input(
        self, expression: SourceExpression, node: ast.Name, visiting: frozenset[tuple[str, int]]
    ) -> None:
        values = self._expand(expression, (), frozenset())
        if not values or any(not isinstance(value.node, ast.Constant) for value in values):
            self._require_unescaped_factory_name(expression.module, node.id, allowed=node)
        for value in values:
            self._require_closed_factory_input(value, visiting)
        return

    def _require_container_input(
        self,
        expression: SourceExpression,
        node: ast.Tuple | ast.List | ast.Set | ast.Dict,
        visiting: frozenset[tuple[str, int]],
    ) -> None:
        children = (*node.keys, *node.values) if isinstance(node, ast.Dict) else node.elts
        for child in children:
            if child is None:
                raise ValueError("open factory input mapping")
            self._require_closed_factory_input(
                SourceExpression(expression.module, child, expression.bindings), visiting
            )
        return

    def _require_enum_input(self, expression: SourceExpression, node: ast.Attribute) -> None:
        owner = self.reference(expression.module, node.value)
        definition = self.classes.get(owner or "")
        if (
            definition is not None
            and any(
                self.reference((owner or "").rpartition(".")[0], base) in {"enum.Enum", "enum.IntEnum", "enum.StrEnum"}
                for base in definition.bases
            )
            and not any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) for item in definition.body)
        ):
            return
        raise ValueError("unknown factory input attribute")

    def _require_nested_input(self, expression: SourceExpression, visiting: frozenset[tuple[str, int]]) -> None:
        owner = self.constructor_reference(expression)
        fields = self.fields(owner or "")
        if not fields or f"{owner}.__post_init__" in self.definitions:
            raise ValueError("unknown nested factory input")
        for field in fields:
            if not isinstance(field.target, ast.Name):
                continue
            value = self._argument(expression, field.target.id)
            if value is None:
                raise ValueError("unknown nested constructor field")
            self._require_closed_factory_input(value, visiting)
        return

    def _require_unescaped_factory_name(self, module: str, name: str, *, allowed: ast.AST | None = None) -> None:
        tree = self.modules[module].tree
        parents = {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not loaded_name(node, name):
                continue
            require_unescaped_use(node, allowed, parents)
        if any(
            binding.target == module and binding.imported_name == name
            for source in self.modules.values()
            for binding in source.bindings.values()
        ):
            raise ValueError("factory source escapes its declaring module")

    def _require_pure_receiver_method(
        self, owner: str, definition: ast.FunctionDef | ast.AsyncFunctionDef, visiting: frozenset[str]
    ) -> None:
        reference = f"{owner}.{definition.name}"
        if reference in visiting or definition.decorator_list:
            raise ValueError("cyclic receiver method")
        visiting = visiting | {reference}
        if any(not pure_return_statement(item) for item in definition.body):
            raise ValueError("factory receiver method is not a pure return")
        module = owner.rpartition(".")[0]
        for statement in definition.body:
            if isinstance(statement, ast.Return) and not isinstance(statement.value, ast.Call):
                raise ValueError("receiver method must return a constructed record")
        for item in ast.walk(definition):
            self._require_pure_receiver_item(owner, module, definition, item, visiting)

    def _require_pure_receiver_item(
        self,
        owner: str,
        module: str,
        definition: ast.FunctionDef | ast.AsyncFunctionDef,
        item: ast.AST,
        visiting: frozenset[str],
    ) -> None:
        if isinstance(item, ast.Name) and item.id == "self":
            parent = next((parent for parent in ast.walk(definition) if item in ast.iter_child_nodes(parent)), None)
            if not isinstance(parent, ast.Attribute) or parent.value is not item:
                raise ValueError("raw factory receiver escapes")
        if not isinstance(item, ast.Call):
            return
        self._require_receiver_call(owner, module, item, visiting)

    def _require_receiver_call(self, owner: str, module: str, item: ast.Call, visiting: frozenset[str]) -> None:
        arguments = (*item.args, *(keyword.value for keyword in item.keywords))
        if any(contains_receiver_value(argument) for argument in arguments):
            called = self.reference(module, item.func) or ""
            if not self.fields(called) and not (
                self.fields(called.rpartition(".")[0]) and pure_record_classmethod(self.definitions.get(called))
            ):
                raise ValueError("factory receiver escapes")
        self._require_receiver_sibling(owner, item, visiting)

    def _require_receiver_sibling(self, owner: str, item: ast.Call, visiting: frozenset[str]) -> None:
        if not isinstance(item.func, ast.Attribute) or not any(
            isinstance(child, ast.Name) and child.id == "self" for child in ast.walk(item.func.value)
        ):
            return
        if not isinstance(item.func.value, ast.Name) or item.func.value.id != "self":
            raise ValueError("factory receiver calls an unknown method")
        sibling = self.definitions.get(f"{owner}.{item.func.attr}")
        if not isinstance(sibling, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ValueError("factory receiver calls an unknown method")
        self._require_pure_receiver_method(owner, sibling, visiting)
