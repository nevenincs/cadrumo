"""Conservative scoped assignment evaluator for closed dynamic import arguments."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass

from .import_evaluation_sequences import sequence_dict_nodes, sequence_literal_nodes, sequence_name_nodes
from .import_evaluation_strings import evaluate_compound, evaluate_joined_string, evaluate_name
from .import_target_value_sets import bounded, combine


@dataclass(frozen=True)
class TargetAssignment:
    """One visible assignment with its tuple projection and source line."""

    lineno: int
    value: ast.AST
    projection: tuple[int, ...] = ()
    unpack: bool = False


class TargetEvaluationContext:
    """Conservative finite-string evaluator for dynamic import arguments."""

    def __init__(self, tree: ast.Module, module_name: str | None = None) -> None:
        """Index lexical parents and assignments for conservative target evaluation."""
        self.module_name = module_name
        self._parents: dict[int, ast.AST] = {}
        self._module_assignments: dict[str, list[TargetAssignment]] = {}
        self._function_assignments: dict[int, dict[str, list[TargetAssignment]]] = {}
        self._function_params: dict[int, set[str]] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                self._parents[id(child)] = parent
        self._collect_assignments(tree)

    def _collect_assignments(self, tree: ast.Module) -> None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                self._function_assignments[id(node)] = {}
                arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                self._function_params[id(node)] = {argument.arg for argument in arguments}
                if node.args.vararg:
                    self._function_params[id(node)].add(node.args.vararg.arg)
                if node.args.kwarg:
                    self._function_params[id(node)].add(node.args.kwarg.arg)
            if isinstance(node, ast.Assign):
                self._save_assignment(node.targets, node.value, node)
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                self._save_assignment((node.target,), node.value, node)
            elif isinstance(node, ast.For):
                self._save_assignment((node.target,), node.iter, node, unpack=True)

    def _save_assignment(
        self, targets: Iterable[ast.expr], value: ast.AST, node: ast.AST, *, unpack: bool = False
    ) -> None:
        scope = self.nearest_function(node)
        target_map = self._module_assignments if scope is None else self._function_assignments.setdefault(id(scope), {})
        for target in targets:
            self._save_target_assignment(target_map, target, value, node, unpack=unpack)

    def _save_target_assignment(
        self,
        target_map: dict[str, list[TargetAssignment]],
        target: ast.expr,
        value: ast.AST,
        node: ast.AST,
        *,
        unpack: bool,
    ) -> None:
        if isinstance(target, ast.Name):
            target_map.setdefault(target.id, []).append(
                TargetAssignment(getattr(node, "lineno", 0), value, unpack=unpack)
            )
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for index, element in enumerate(target.elts):
                self._save_target_projection(target_map, element, value, node, (index,), unpack=unpack)

    def _save_target_projection(
        self,
        target_map: dict[str, list[TargetAssignment]],
        target: ast.expr,
        value: ast.AST,
        node: ast.AST,
        projection: tuple[int, ...],
        *,
        unpack: bool,
    ) -> None:
        if isinstance(target, ast.Name):
            target_map.setdefault(target.id, []).append(
                TargetAssignment(getattr(node, "lineno", 0), value, projection, unpack)
            )
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            for index, element in enumerate(target.elts):
                self._save_target_projection(target_map, element, value, node, (*projection, index), unpack=unpack)

    def nearest_function(self, node: ast.AST) -> ast.AST | None:
        """Find the enclosing callable scope for an expression."""
        parent = self._parents.get(id(node))
        while parent is not None:
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                return parent
            parent = self._parents.get(id(parent))
        return None

    def values_for(self, node: ast.AST | None, lineno: int) -> frozenset[str] | None:
        """Evaluate a target expression in its original lexical scope."""
        if node is None:
            return None
        return self.evaluate_values(node, lineno, set(), self.nearest_function(node))

    def evaluate_values(
        self,
        node: ast.AST,
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> frozenset[str] | None:
        """Evaluate supported finite string expressions in branch order."""
        if isinstance(node, ast.Constant):
            value = node.value
            return frozenset({value}) if isinstance(value, str) else None
        if isinstance(node, ast.Name):
            return evaluate_name(self, node, lineno, resolving, scope)
        if isinstance(node, ast.JoinedStr):
            return evaluate_joined_string(self, node, lineno, resolving, scope)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return combine(
                self.evaluate_values(node.left, lineno, resolving, scope),
                self.evaluate_values(node.right, lineno, resolving, scope),
            )
        return evaluate_compound(self, node, lineno, resolving, scope)

    def unpacked_values(
        self,
        node: ast.AST,
        projection: tuple[int, ...],
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> frozenset[str] | None:
        """Evaluate a finite iterable assignment made by tuple unpacking."""
        elements = self.sequence_nodes(node, lineno, resolving, scope)
        if elements is None:
            return None
        result: set[str] = set()
        for element in elements:
            values = self.values_at_indices(element, projection, lineno, resolving, scope)
            if values is None:
                return None
            result.update(values)
        return bounded(result)

    def values_at_indices(
        self,
        node: ast.AST,
        indexes: tuple[int, ...],
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> frozenset[str] | None:
        """Evaluate one finite tuple/list/dict-items projection."""
        if not indexes:
            return self.evaluate_values(node, lineno, resolving, scope)
        elements = self.sequence_nodes(node, lineno, resolving, scope)
        if elements is None or indexes[0] >= len(elements):
            return None
        return self.values_at_indices(elements[indexes[0]], indexes[1:], lineno, resolving, scope)

    def sequence_nodes(
        self,
        node: ast.AST,
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> tuple[ast.AST, ...] | None:
        """Expand supported finite iterable syntax and assignment chains."""
        if isinstance(node, (ast.Tuple, ast.List)):
            return sequence_literal_nodes(self, node, lineno, resolving, scope)
        if isinstance(node, ast.Dict):
            return sequence_dict_nodes(self, node, lineno, resolving, scope)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "items":
            if node.args or node.keywords:
                return None
            return self.sequence_nodes(node.func.value, lineno, resolving, scope)
        if isinstance(node, ast.Name):
            return sequence_name_nodes(self, node, lineno, resolving, scope)
        return None

    def sequence_values(
        self,
        node: ast.AST,
        lineno: int,
        resolving: set[tuple[int, str]],
        scope: ast.AST | None,
    ) -> tuple[str, ...] | None:
        """Evaluate finite iterable string values in source order."""
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values: list[str] = []
            for element in node.elts:
                evaluated = self.evaluate_values(element, lineno, resolving, scope)
                if evaluated is None:
                    return None
                values.extend(sorted(evaluated))
            return tuple(values)
        if isinstance(node, ast.Name):
            assignments = self.latest_values(node.id, lineno, scope)
            if not assignments:
                return None
            result: list[str] = []
            for assignment in assignments:
                evaluated_sequence = self.sequence_values(assignment.value, assignment.lineno - 1, resolving, scope)
                if evaluated_sequence is None:
                    return None
                result.extend(evaluated_sequence)
            return tuple(result)
        return None

    def latest_values(self, name: str, lineno: int, scope: ast.AST | None) -> tuple[TargetAssignment, ...] | None:
        """Collect visible assignments before the target source line."""
        if scope is not None:
            if name in self._function_params.get(id(scope), set()):
                return None
            local = tuple(
                assignment
                for assignment in self._function_assignments.get(id(scope), {}).get(name, ())
                if assignment.lineno <= lineno
            )
            if local:
                return local
        module = tuple(
            assignment for assignment in self._module_assignments.get(name, ()) if assignment.lineno <= lineno
        )
        return module or None
