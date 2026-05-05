"""Relation helpers for cross-model registry dependencies."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ._errors import RegistryValidationError
from ._schema import ModeloRevision, RelationDefinition

__all__ = [
    "RegistryRelationSourceRequirement",
    "RelationDefinition",
    "relation_source_requirements",
    "resolve_relation_values",
]


class RegistryRelationSourceRequirement(BaseModel):
    """External source filings required by one or more registry relations."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    periods: tuple[str, ...] = Field(min_length=1)
    source_output: str = Field(min_length=1)
    relation_ids: tuple[str, ...] = Field(min_length=1)
    target_bindings: tuple[str, ...] = Field(min_length=1)
    dependency_role: str = Field(min_length=1)
    aggregation_op: str = Field(min_length=1)


def relation_source_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryRelationSourceRequirement, ...]:
    """Return source declarations needed to resolve relations for a filing."""

    grouped: dict[tuple[str, int, tuple[str, ...], str, str, str], dict[str, set[str]]] = {}
    for relation in revision.relations:
        if relation.target_periods and period not in relation.target_periods:
            continue
        source_year = _relation_source_year(relation, filing_year=filing_year)
        source_periods = relation.source_periods or (period,)
        key = (
            str(relation.source_modelo),
            source_year,
            tuple(source_periods),
            str(relation.source_output),
            str(relation.dependency_role),
            str((relation.aggregation or {}).get("op", "copy")),
        )
        bucket = grouped.setdefault(key, {"relation_ids": set(), "target_bindings": set()})
        bucket["relation_ids"].add(str(relation.id))
        bucket["target_bindings"].add(str(relation.target_binding))
    return tuple(
        RegistryRelationSourceRequirement(
            source_modelo=source_modelo,
            filing_year=source_year,
            periods=source_periods,
            source_output=source_output,
            relation_ids=tuple(sorted(values["relation_ids"])),
            target_bindings=tuple(sorted(values["target_bindings"])),
            dependency_role=dependency_role,
            aggregation_op=aggregation_op,
        )
        for (
            source_modelo,
            source_year,
            source_periods,
            source_output,
            dependency_role,
            aggregation_op,
        ), values in sorted(grouped.items())
    )


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


def _relation_source_year(relation: RelationDefinition, *, filing_year: int) -> int:
    selector = relation.source_revision_selector
    if "year" in selector:
        year = selector["year"]
        if not isinstance(year, int):
            raise RegistryValidationError(f"relation {relation.id!r} source selector year must be an integer")
        return year
    delta = selector.get("filing_year_delta", 0)
    if not isinstance(delta, int):
        raise RegistryValidationError(f"relation {relation.id!r} source selector filing_year_delta must be an integer")
    return filing_year + delta
