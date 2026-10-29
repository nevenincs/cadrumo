"""Read-only recursive dataclass-walk provenance."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .import_module_syntax import qualified_name
from .import_record_models import SourceExpression
from .import_record_values import DeclarationValues


class DeclarationWalks(DeclarationValues):
    """Trace finite declaration walks without executing product code."""

    def _walked_records(
        self,
        module: str,
        reference: str,
        definition: ast.FunctionDef | ast.AsyncFunctionDef,
        bindings: Mapping[str, tuple[SourceExpression, ...]],
        path: tuple[str, ...],
        visiting: frozenset[tuple[str, int, tuple[str, ...]]],
    ) -> tuple[SourceExpression, ...]:
        parameter = _walk_parameter(definition, bindings)
        yielded = False
        guarded = False
        for node in ast.walk(definition):
            if self.context(module).nearest_function(node) is not definition:
                continue
            node_yielded, node_guarded = self._check_walk_node(module, reference, definition, parameter, node)
            yielded |= node_yielded
            guarded |= node_guarded
        if not yielded or not guarded:
            raise ValueError("not a closed module-record walk")
        leaves = tuple(leaf for source in bindings[parameter] for leaf in self._record_leaves(source, frozenset()))
        return tuple(item for leaf in leaves for item in self._expand(leaf, path, visiting))

    def _check_walk_node(
        self,
        module: str,
        reference: str,
        definition: ast.FunctionDef | ast.AsyncFunctionDef,
        parameter: str,
        node: ast.AST,
    ) -> tuple[bool, bool]:
        yielded = False
        if isinstance(node, ast.Yield):
            if not isinstance(node.value, ast.Name) or node.value.id != parameter:
                raise ValueError("record walk injects another source")
            yielded = True
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            raise ValueError("record walk mutates its source")
        if isinstance(node, ast.YieldFrom):
            self._check_walk_delegate(module, reference, definition, parameter, node)
        guarded = self._walk_guard(module, parameter, node)
        self._check_walk_escape(module, parameter, node)
        return yielded, guarded

    def _check_walk_delegate(
        self,
        module: str,
        reference: str,
        definition: ast.FunctionDef | ast.AsyncFunctionDef,
        parameter: str,
        node: ast.YieldFrom,
    ) -> None:
        if (
            not isinstance(node.value, ast.Call)
            or self.reference(module, node.value.func) != reference
            or len(node.value.args) != 1
        ):
            raise ValueError("record walk delegates to unknown source")
        argument = node.value.args[0]
        if isinstance(argument, ast.Name):
            _check_walk_loop(definition, parameter, argument)
        elif _field_selector(argument, parameter):
            self._check_field_loop(module, definition, parameter, argument)
        else:
            raise ValueError("walk injects a recursive input")

    def _check_field_loop(
        self, module: str, definition: ast.FunctionDef | ast.AsyncFunctionDef, parameter: str, argument: ast.expr
    ) -> None:
        if not isinstance(argument, ast.Call):
            raise ValueError("walk injects a recursive input")
        attribute = argument.args[1]
        if (
            not isinstance(attribute, ast.Attribute)
            or attribute.attr != "name"
            or not isinstance(attribute.value, ast.Name)
        ):
            raise ValueError("unknown recursive field selector")
        loops = _named_loops(definition, attribute.value.id)
        if not loops or any(not self._field_iterator(module, loop.iter, parameter) for loop in loops):
            raise ValueError("unknown recursive field source")

    def _field_iterator(self, module: str, iterator: ast.expr, parameter: str) -> bool:
        return (
            isinstance(iterator, ast.Call)
            and self.reference(module, iterator.func) == "dataclasses.fields"
            and len(iterator.args) == 1
            and isinstance(iterator.args[0], ast.Name)
            and iterator.args[0].id == parameter
        )

    def _walk_guard(self, module: str, parameter: str, node: ast.AST) -> bool:
        if not _is_type_guard(node, parameter):
            return False
        if not isinstance(node, ast.Call):
            return False
        fields = self.fields(self.reference(module, node.args[1]) or "")
        return any(isinstance(item.target, ast.Name) and item.target.id == "module" for item in fields)

    def _check_walk_escape(self, module: str, parameter: str, node: ast.AST) -> None:
        if not isinstance(node, ast.Call) or not any(
            isinstance(argument, ast.Name) and argument.id == parameter for argument in node.args
        ):
            return
        function = qualified_name(node.func)
        canonical = self.reference(module, node.func)
        if function not in {"isinstance", "enumerate", "getattr"} and canonical not in {
            "dataclasses.is_dataclass",
            "dataclasses.fields",
        }:
            raise ValueError("record walk escapes its source")

    def _record_leaves(
        self, source: SourceExpression, visiting: frozenset[tuple[str, int]]
    ) -> tuple[SourceExpression, ...]:
        key = (source.module, id(source.node))
        if key in visiting or len(visiting) > 80:
            raise ValueError("unbounded record walk")
        leaves: list[SourceExpression] = []
        for expression in self._expand(source, (), frozenset()):
            reference = self.constructor_reference(expression)
            fields = self.fields(reference or "")
            if any(isinstance(item.target, ast.Name) and item.target.id == "module" for item in fields):
                leaves.append(expression)
                continue
            if not fields:
                raise ValueError("unknown record walk member")
            self._collect_record_fields(expression, reference, fields, visiting | {key}, leaves)
        return tuple(leaves)

    def _collect_record_fields(
        self,
        expression: SourceExpression,
        reference: str | None,
        fields: tuple[ast.AnnAssign, ...],
        visiting: frozenset[tuple[str, int]],
        leaves: list[SourceExpression],
    ) -> None:
        for field in fields:
            if not isinstance(field.target, ast.Name) or (reference or "", field.target.id) not in self.target_fields:
                continue
            child = self._argument(expression, field.target.id)
            if child is None:
                raise ValueError("unknown record walk field")
            leaves.extend(self._record_leaves(child, visiting))


def _named_loops(definition: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> list[ast.For]:
    return [
        loop
        for loop in ast.walk(definition)
        if isinstance(loop, ast.For) and isinstance(loop.target, ast.Name) and loop.target.id == name
    ]


def _check_walk_loop(definition: ast.FunctionDef | ast.AsyncFunctionDef, parameter: str, argument: ast.Name) -> None:
    loops = _named_loops(definition, argument.id)
    if argument.id != parameter and not loops:
        raise ValueError("unknown recursive walk input")
    for loop in loops:
        iterator = loop.iter
        if (
            isinstance(iterator, ast.Call)
            and isinstance(iterator.func, ast.Attribute)
            and iterator.func.attr in {"values", "items"}
        ):
            iterator = iterator.func.value
        if not isinstance(iterator, ast.Name) or iterator.id != parameter:
            raise ValueError("walk loop has unrelated source")


def _field_selector(argument: ast.expr, parameter: str) -> bool:
    return (
        isinstance(argument, ast.Call)
        and isinstance(argument.func, ast.Name)
        and argument.func.id == "getattr"
        and len(argument.args) == 2
        and isinstance(argument.args[0], ast.Name)
        and argument.args[0].id == parameter
    )


def _is_type_guard(node: ast.AST, parameter: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "isinstance"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == parameter
    )


def _walk_parameter(
    definition: ast.FunctionDef | ast.AsyncFunctionDef, bindings: Mapping[str, tuple[SourceExpression, ...]]
) -> str:
    parameters = (*definition.args.posonlyargs, *definition.args.args)
    if not parameters or parameters[0].arg not in bindings:
        raise ValueError("unknown record walk input")
    return parameters[0].arg
