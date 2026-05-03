"""Relation helpers for cross-model registry dependencies."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from ._errors import RegistryValidationError
from ._schema import ModeloRevision, RelationDefinition

__all__ = ["RelationDefinition", "resolve_relation_values"]


def resolve_relation_values(
    revision: ModeloRevision,
    external_outputs: Mapping[str, Decimal | tuple[Decimal, ...]],
) -> dict[str, Decimal]:
    """Resolve typed relation values from caller-supplied external outputs.

    ``external_outputs`` is keyed by relation id. Aggregation defaults to copy;
    ``{"op": "sum"}`` sums tuple values for annual summaries.
    """

    relation_ids = {relation.id for relation in revision.relations}
    unknown = sorted(set(external_outputs).difference(relation_ids))
    if unknown:
        raise RegistryValidationError(f"unknown relation ids: {unknown!r}")
    resolved: dict[str, Decimal] = {}
    for relation in revision.relations:
        if relation.id not in external_outputs:
            raise RegistryValidationError(f"missing relation value for {relation.id!r}")
        raw_value = external_outputs[relation.id]
        op = str((relation.aggregation or {}).get("op", "copy"))
        if op == "copy":
            if not isinstance(raw_value, Decimal):
                raise RegistryValidationError(f"relation {relation.id!r} copy requires one Decimal")
            resolved[relation.id] = raw_value
        elif op == "sum":
            if not isinstance(raw_value, tuple) or not all(isinstance(value, Decimal) for value in raw_value):
                raise RegistryValidationError(f"relation {relation.id!r} sum requires a tuple of Decimal values")
            resolved[relation.id] = sum(raw_value, Decimal("0"))
        else:
            raise RegistryValidationError(f"relation {relation.id!r} uses unsupported aggregation op {op!r}")
    return resolved
