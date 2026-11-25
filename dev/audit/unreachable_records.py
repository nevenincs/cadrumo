"""Resolve whole enum and named-tuple consumers by their declared record owner."""

from __future__ import annotations

import ast
from collections.abc import Mapping

from .unreachable_frameworks import expression_name, import_bindings
from .unreachable_member_models import ResolvedCall
from .unreachable_members import resolved_member_uses
from .unreachable_models import ShippedModule
from .unreachable_receiver_types import receiver_types


def record_member_uses(modules: Mapping[str, ShippedModule], consumers: frozenset[str]) -> frozenset[tuple[str, str]]:
    """Serialization consumes named-tuple fields; whole enum reads consume members.

    Constructing a named tuple, importing a class, or using an unrelated
    ``_asdict`` method does not prove that the declared fields are read.
    """
    tuples, enums = _record_definitions(modules)

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


def _record_definitions(
    modules: Mapping[str, ShippedModule],
) -> tuple[dict[str, frozenset[tuple[str, str]]], dict[str, frozenset[tuple[str, str]]]]:
    tuples: dict[str, frozenset[tuple[str, str]]] = {}
    enums: dict[str, frozenset[tuple[str, str]]] = {}
    for name, module in modules.items():
        bindings = import_bindings(module)
        for node in module.tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            _index_record(name, node, bindings, tuples, enums)
    return tuples, enums


def _index_record(
    name: str,
    node: ast.ClassDef,
    bindings: Mapping[str, str],
    tuples: dict[str, frozenset[tuple[str, str]]],
    enums: dict[str, frozenset[tuple[str, str]]],
) -> None:
    bases: set[str] = set()
    for base in node.bases:
        head, separator, tail = expression_name(base).partition(".")
        bases.add(f"{bindings.get(head, f'{name}.{head}')}{separator}{tail}")
    named_tuple = "typing.NamedTuple" in bases
    enum = bool(bases & {f"enum.{base}" for base in ("Enum", "StrEnum", "IntEnum", "Flag", "IntFlag")})
    if not named_tuple and not enum:
        return
    members = _record_members(name, node)
    (tuples if named_tuple else enums)[f"{name}.{node.name}"] = members


def _record_members(name: str, node: ast.ClassDef) -> frozenset[tuple[str, str]]:
    members = frozenset(
        (name, f"{node.name}.{target.id}")
        for member in node.body
        if isinstance(member, ast.AnnAssign | ast.Assign)
        for target in (member.targets if isinstance(member, ast.Assign) else [member.target])
        if isinstance(target, ast.Name) and not target.id.startswith("_")
    )
    return members
