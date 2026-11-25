"""Resolve member consumers on imported classes and explicitly typed local bindings."""

from __future__ import annotations

import ast

from .unreachable_frameworks import import_bindings
from .unreachable_member_models import ResolvedCall
from .unreachable_member_walk import MemberWalk
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import ReceiverTypes


def resolved_member_uses(
    module: ShippedModule,
    known: frozenset[str],
    *,
    calls: list[ResolvedCall] | None = None,
    receivers: ReceiverTypes | None = None,
    whole_uses: set[str] | None = None,
) -> set[tuple[str, str]]:
    """Keep member identities qualified; a same-named attribute cannot clear one.

    Only imported classes, constructor assignments and explicit annotations
    establish an owner. Arbitrary call results and unresolved receivers remain
    candidates. Scope-local names do not escape into sibling functions.
    """
    visitor = MemberWalk(module, known, calls, receivers, whole_uses)
    initial = import_bindings(module)
    initial.update(
        (node.name, f"{module.name}.{node.name}")
        for node in module.tree.body
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    )
    visitor.walk(module.tree.body, initial)
    return visitor.uses


def resolved_calls(
    module: ShippedModule, known: frozenset[str], receivers: ReceiverTypes | None = None
) -> tuple[ResolvedCall, ...]:
    """Resolve callable and argument identities using the same lexical scope walk."""
    calls: list[ResolvedCall] = []
    resolved_member_uses(module, known, calls=calls, receivers=receivers)
    return tuple(calls)
