"""Bounded receiver provenance for dynamic imports."""

from __future__ import annotations

import ast

from .import_record_definitions import field_names
from .import_record_models import SourceExpression
from .import_record_sources import RecordSourceProvenance


class RecordGraphProvenance(RecordSourceProvenance):
    """Resolve graph, mapping, and constructor declaration projections."""

    def _expand_call(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if not isinstance(node, ast.Call):
            raise ValueError("expected call")
        reference = self.constructor_reference(expression)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            return self._expand_mapping_get(expression, node, node.func, path, visiting)
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"values", "items"}:
            return self._expand(
                SourceExpression(expression.module, node.func.value, expression.bindings), path, visiting
            )
        if isinstance(node.func, ast.Attribute) and node.func.attr in {
            "root",
            "spec",
            "children",
            "nodes",
            "resolve_path",
            "by_schema_identity",
            "by_key",
        }:
            graph = self._expand_graph_call(expression, node.func, path, visiting)
            if graph is not None:
                return graph
        if reference in self.classes:
            return self._expand_constructor(expression, reference, path, visiting)
        return self._expand_factory_call(expression, node, reference, path, visiting)

    def _expand_factory_call(
        self,
        expression: SourceExpression,
        node: ast.Call,
        reference: str | None,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id in {"tuple", "list", "set", "frozenset"}
            and len(node.args) == 1
        ):
            return self._expand(SourceExpression(expression.module, node.args[0], expression.bindings), path, visiting)
        if reference == "dataclasses.replace":
            return self._replace_sources(expression, path, visiting)
        definition = self.definitions.get(reference or "")
        if not isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound = self._bound_method_results(expression, path, visiting)
            if bound is not None:
                return bound
            raise ValueError(f"unknown declaration constructor in {expression.module}:{getattr(node, 'lineno', 0)}")
        return self._factory_results(expression, reference or "", definition, path, visiting)

    def _expand_graph_call(
        self,
        expression: SourceExpression,
        function: ast.Attribute,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...] | None:
        objects = self._expand(SourceExpression(expression.module, function.value, expression.bindings), (), visiting)
        if objects and all(self._is_graph(obj) for obj in objects):
            suffix = _graph_suffix(function.attr, path)
            if function.attr == "root":
                return self._expand_graph_roots(objects, suffix, visiting)
            records = tuple(item for obj in objects for item in self._graph_records(obj, suffix, visiting))
            if function.attr == "nodes" and not path:
                return tuple(
                    SourceExpression(item.module, item.node, item.bindings, wrapped_node=True) for item in records
                )
            return records
        return None

    def _is_graph(self, obj: SourceExpression) -> bool:
        names = {
            item.target.id
            for item in self.fields(self.constructor_reference(obj) or "")
            if isinstance(item.target, ast.Name)
        }
        return {"declared", "families", "resolver"} <= names

    def _expand_graph_roots(
        self,
        objects: tuple[SourceExpression, ...],
        suffix: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        roots = [self._argument(obj, "declared") for obj in objects]
        if any(root is None for root in roots):
            raise ValueError("unknown graph root")
        return tuple(item for root in roots if root is not None for item in self._expand(root, suffix, visiting))

    def _expand_mapping_get(
        self,
        expression: SourceExpression,
        node: ast.Call,
        function: ast.Attribute,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        mappings = self._expand(SourceExpression(expression.module, function.value, expression.bindings), (), visiting)
        values: list[SourceExpression] = []
        for mapping in mappings:
            if not isinstance(mapping.node, ast.Dict):
                raise ValueError("unknown dictionary source")
            values.extend(SourceExpression(mapping.module, value, mapping.bindings) for value in mapping.node.values)
        if len(node.args) > 1:
            values.append(SourceExpression(expression.module, node.args[1], expression.bindings))
        return tuple(item for value in values for item in self._expand(value, path, visiting))

    def _expand_constructor(
        self,
        expression: SourceExpression,
        reference: str,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        if not self.fields(reference):
            raise ValueError("unproven custom constructor")
        if not path:
            return (expression,)
        fields = {item.target.id for item in self.fields(reference) if isinstance(item.target, ast.Name)}
        if path[0] == "specs" and {"declared", "families", "resolver"} <= fields:
            return self._graph_records(expression, path[1:], visiting)
        field_value = self._argument(expression, path[0])
        if field_value is None:
            raise ValueError("unknown constructor field")
        if path == ("module",):
            values = self._record_modules(expression)
            return tuple(SourceExpression(expression.module, ast.Constant(value=value)) for value in values)
        return self._expand(field_value, path[1:], visiting)

    def _graph_records(
        self, graph: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        declared = self._argument(graph, "declared")
        families = self._argument(graph, "families")
        if declared is None or families is None:
            raise ValueError("unknown graph declaration")
        result = list(self._expand(declared, path, visiting))
        for family in self._expand(families, (), visiting):
            source = self._argument(family, "source")
            if source is None:
                raise ValueError("unknown graph family")
            for target in self._expand(source, (), visiting):
                modules = self._record_modules(target)
                qualname = self._argument(target, "qualname")
                names = self._strings(qualname) if qualname is not None else None
                if names is None:
                    raise ValueError("unknown graph family symbol")
                for module in modules:
                    for name in names:
                        result.extend(self._expand(self._module_assignment(module, name), path, visiting))
        return tuple(result)

    def _replace_sources(
        self, expression: SourceExpression, path: tuple[str, ...], visiting: frozenset[tuple[str, int, tuple[str, ...]]]
    ) -> tuple[SourceExpression, ...]:
        node = expression.node
        if not isinstance(node, ast.Call) or len(node.args) != 1:
            raise ValueError("unsupported record replacement")
        originals = self._expand(SourceExpression(expression.module, node.args[0], expression.bindings), (), visiting)
        updated: list[SourceExpression] = []
        for original in originals:
            updated.extend(self._replace_one(expression, node, original, path, visiting))
        return tuple(updated)

    def _replace_one(
        self,
        expression: SourceExpression,
        node: ast.Call,
        original: SourceExpression,
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        if not isinstance(original.node, ast.Call):
            raise ValueError("unknown replacement source")
        bindings = dict(original.bindings)
        changed = {keyword.arg for keyword in node.keywords}
        keywords = [keyword for keyword in original.node.keywords if keyword.arg not in changed]
        reference = self.constructor_reference(original)
        fields = field_names(self.fields(reference or ""))
        arguments = list(original.node.args)
        for index, keyword in enumerate(node.keywords):
            if keyword.arg is None:
                raise ValueError("open replacement fields")
            name = f"replacement_{id(node)}_{index}"
            bindings[name] = (SourceExpression(expression.module, keyword.value, expression.bindings),)
            value = ast.Name(id=name, ctx=ast.Load())
            if keyword.arg in fields and fields.index(keyword.arg) < len(arguments):
                arguments[fields.index(keyword.arg)] = value
            else:
                keywords.append(ast.keyword(arg=keyword.arg, value=value))
        call = ast.Call(func=original.node.func, args=arguments, keywords=keywords)
        return self._expand(SourceExpression(original.module, call, bindings), path, visiting)


def _graph_suffix(attribute: str, path: tuple[str, ...]) -> tuple[str, ...]:
    return path[1:] if attribute == "nodes" and path and path[0] == "spec" else path
