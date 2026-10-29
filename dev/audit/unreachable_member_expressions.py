"""Resolve statically typed receiver expressions and guards."""

from __future__ import annotations

import ast
import warnings
from collections.abc import Sequence

from .unreachable_receiver_types import ReceiverTypes


class MemberExpressionResolver:
    """Resolve expressions against explicit receiver facts."""

    def __init__(self, receivers: ReceiverTypes | None) -> None:
        """Bind the available receiver types."""
        self.receivers = receivers

    def _expression(self, node: ast.expr, bindings: dict[str, str], containers: dict[str, str] | None = None) -> str:
        if isinstance(node, ast.Name):
            target = bindings.get(node.id, "")
            return self.receivers.values.get(target, target) if self.receivers is not None else target
        if isinstance(node, ast.Attribute):
            return self._attribute(node, bindings, containers)
        if isinstance(node, ast.Call) and self.receivers is not None:
            return self.receivers.returns.get(self._expression(node.func, bindings, containers), "")
        if isinstance(node, ast.Subscript):
            return self._subscript(node, bindings, containers)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return self._string_expression(node.value, bindings, containers)
        return ""

    def _attribute(self, node: ast.Attribute, bindings: dict[str, str], containers: dict[str, str] | None) -> str:
        owner = self._expression(node.value, bindings, containers)
        if self.receivers is not None:
            owner = self.receivers.fields.get(owner, owner)
        return f"{owner}.{node.attr}" if owner else ""

    def _string_expression(self, value: str, bindings: dict[str, str], containers: dict[str, str] | None) -> str:
        # Any string constant is probed here, regex patterns included; an
        # invalid escape such as ``\d`` is prose, not a type expression,
        # and must not print a SyntaxWarning into the gate's output.
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            try:
                parsed = ast.parse(value, mode="eval").body
            except (SyntaxError, SyntaxWarning):
                return ""
        return self._expression(parsed, bindings, containers)

    def _subscript(self, node: ast.Subscript, bindings: dict[str, str], containers: dict[str, str] | None) -> str:
        if (
            not isinstance(node.slice, ast.Slice)
            and isinstance(node.value, ast.Name)
            and (containers is not None and containers)
            and ((item_type := containers.get(node.value.id)) is not None and item_type)
        ):
            return item_type
        return self._expression(node.value, bindings, containers)

    def _narrow(self, condition: ast.expr, bindings: dict[str, str]) -> None:
        """Use an explicit builtin isinstance guard, never an arbitrary predicate."""
        if (
            self.receivers is not None
            and isinstance(condition, ast.Call)
            and isinstance(condition.func, ast.Name)
            and condition.func.id == "isinstance"
            and "isinstance" not in bindings
            and len(condition.args) == 2
            and isinstance(condition.args[0], ast.Name)
            and (owner := self._expression(condition.args[1], bindings)) in self.receivers.classes
        ):
            bindings[condition.args[0].id] = owner

    def _element(self, node: ast.expr, bindings: dict[str, str], containers: dict[str, str]) -> str:
        if self.receivers is None:
            return ""
        if isinstance(node, ast.Name) and node.id in containers:
            return containers[node.id]
        if isinstance(node, ast.ListComp | ast.SetComp | ast.GeneratorExp) and len(node.generators) == 1:
            generator = node.generators[0]
            if not isinstance(generator.target, ast.Name):
                return ""
            local = dict(bindings)
            local[generator.target.id] = self._element(generator.iter, bindings, containers)
            for condition in generator.ifs:
                self._narrow(condition, local)
            result = self._expression(node.elt, local, containers)
            return result if result in self.receivers.classes else ""
        target = self._expression(node.func if isinstance(node, ast.Call) else node, bindings, containers)
        return self.receivers.iterables.get(target, "")


def bind_targets(
    targets: Sequence[ast.expr], owner: str, item_type: str, bindings: dict[str, str], containers: dict[str, str]
) -> None:
    """Record qualified owners for assignment targets."""
    for target in targets:
        if isinstance(target, ast.Name):
            bindings[target.id] = ""
            containers.pop(target.id, None)
            if owner and not item_type:
                bindings[target.id] = owner
            if item_type:
                containers[target.id] = item_type
