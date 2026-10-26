"""Resolve whole enum and named-tuple consumers by their declared record owner."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .unreachable_frameworks import _expression_name, _import_bindings
from .unreachable_members import ResolvedCall, resolved_member_uses
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import receiver_types


def record_member_uses(modules: Mapping[str, ShippedModule], consumers: frozenset[str]) -> frozenset[tuple[str, str]]:
    """Serialization consumes named-tuple fields; whole enum reads consume members.

    Constructing a named tuple, importing a class, or using an unrelated
    ``_asdict`` method does not prove that the declared fields are read.
    """
    tuples: dict[str, frozenset[tuple[str, str]]] = {}
    enums: dict[str, frozenset[tuple[str, str]]] = {}
    for name, module in modules.items():
        bindings = _import_bindings(module)
        for node in module.tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases: set[str] = set()
            for base in node.bases:
                head, separator, tail = _expression_name(base).partition(".")
                bases.add(f"{bindings.get(head, f'{name}.{head}')}{separator}{tail}")
            named_tuple = "typing.NamedTuple" in bases
            enum = bool(bases & {f"enum.{base}" for base in ("Enum", "StrEnum", "IntEnum", "Flag", "IntFlag")})
            if not named_tuple and not enum:
                continue
            members = frozenset(
                (name, f"{node.name}.{target.id}")
                for member in node.body
                if isinstance(member, ast.AnnAssign | ast.Assign)
                for target in (member.targets if isinstance(member, ast.Assign) else [member.target])
                if isinstance(target, ast.Name) and not target.id.startswith("_")
            )
            (tuples if named_tuple else enums)[f"{name}.{node.name}"] = members

    receivers = receiver_types(modules)
    known = frozenset(modules)
    uses: set[tuple[str, str]] = set()
    for name in consumers:
        calls: list[ResolvedCall] = []
        whole: set[str] = set()
        resolved_member_uses(modules[name], known, calls=calls, receivers=receivers, whole_uses=whole)
        for call in calls:
            owner, _, method = call.target.rpartition(".")
            if method == "_asdict":
                uses.update(tuples.get(owner, ()))
            whole.add(call.target)
        for owner in whole:
            uses.update(enums.get(owner, ()))
    return frozenset(uses)
