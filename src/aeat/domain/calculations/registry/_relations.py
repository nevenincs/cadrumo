"""Relation helpers for cross-model registry dependencies.

Resolves cross-modelo source requirements and materialises relation values
for a :class:`ModeloRevision` filing. Relations declare which source filings
and output casillas must be available before the target modelo can be
calculated.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from pydantic import BaseModel, Field

from ....core import STRICT_FROZEN_CONFIG, Period
from ._bindings import RegistryModeloObservation
from ._errors import RegistryValidationError
from ._period_offset_math import apply_period_offset
from ._schema import ModeloRevision, RelationDefinition, filing_period_from_scope

__all__ = [
    "RegistryRelationSourceRequirement",
    "RelationDefinition",
    "relation_source_requirements",
    "resolve_relation_values",
    "resolve_relation_values_from_observations",
]


class RegistryRelationSourceRequirement(BaseModel):
    """External source filings required by one or more registry relations."""

    model_config = STRICT_FROZEN_CONFIG

    source_modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=2000, le=2099)
    filing_periods: tuple[Period, ...] = ()
    periods: tuple[str, ...] = Field(min_length=1)
    source_output: str = Field(min_length=1)
    relation_ids: tuple[str, ...] = Field(min_length=1)
    target_bindings: tuple[str, ...] = Field(min_length=1)
    dependency_role: str = Field(min_length=1)
    dependency_treatment: str = Field(min_length=1)
    aggregation_op: str = Field(min_length=1)


def relation_source_requirements(
    revision: ModeloRevision,
    *,
    filing_year: int,
    period: str,
) -> tuple[RegistryRelationSourceRequirement, ...]:
    """Return :class:`RegistryRelationSourceRequirement` items needed to resolve relations for a filing.

    Args:
        revision: The :class:`ModeloRevision` whose relation declarations to inspect.
        filing_year: Target filing year; combined with each relation's source
            offset to derive the expected source-modelo filing year.
        period: Target period token; filters relations by ``target_periods``
            and seeds the source-period derivation.
    """
    classifications_by_source = {
        classification.source_modelo: classification for classification in revision.dependency_classifications
    }
    grouped: dict[tuple[str, int, tuple[str, ...], str, str, str, str], dict[str, set[str]]] = {}
    for relation in revision.relations:
        if relation.target_periods and period not in relation.target_periods:
            continue
        classification = classifications_by_source.get(relation.source_modelo)
        if classification is None:
            raise RegistryValidationError(
                f"relation {relation.id!r} source modelo {relation.source_modelo!r} has no dependency classification",
            )
        if relation.source_period_offset_from_target is not None:
            derived = _derive_offset_source_anchor(relation, target_period=period)
            if derived is None:
                continue
            period_year_delta, source_period = derived
            source_year = _relation_source_year(relation, filing_year=filing_year) + period_year_delta
            source_periods = (source_period,)
        else:
            source_year = _relation_source_year(relation, filing_year=filing_year)
            source_periods = relation.source_periods or (period,)
        key = (
            relation.source_modelo,
            source_year,
            tuple(source_periods),
            relation.source_output,
            relation.dependency_role,
            str(classification.treatment),
            str((relation.aggregation or {}).get("op", "copy")),
        )
        bucket = grouped.setdefault(key, {"relation_ids": set(), "target_bindings": set()})
        bucket["relation_ids"].add(str(relation.id))
        bucket["target_bindings"].add(str(relation.target_binding))
    return tuple(
        RegistryRelationSourceRequirement(
            source_modelo=source_modelo,
            filing_year=source_year,
            filing_periods=tuple(
                filing_period
                for source_period in source_periods
                if (filing_period := filing_period_from_scope(source_year, source_period)) is not None
            ),
            periods=source_periods,
            source_output=source_output,
            relation_ids=tuple(sorted(values["relation_ids"])),
            target_bindings=tuple(sorted(values["target_bindings"])),
            dependency_role=dependency_role,
            dependency_treatment=dependency_treatment,
            aggregation_op=aggregation_op,
        )
        for (
            source_modelo,
            source_year,
            source_periods,
            source_output,
            dependency_role,
            dependency_treatment,
            aggregation_op,
        ), values in sorted(grouped.items())
    )


def resolve_relation_values(
    revision: ModeloRevision,
    external_outputs: Mapping[str, Decimal | tuple[Decimal, ...]],
    *,
    period: str | None = None,
) -> dict[str, Decimal]:
    """Resolve typed relation values from caller-supplied external outputs.

    ``external_outputs`` is keyed by relation id. Aggregation defaults to copy;
    ``{"op": "sum"}`` sums tuple values for annual summaries.

    Args:
        revision: The :class:`ModeloRevision` whose relation definitions are
            resolved against the supplied external outputs.
        external_outputs: Caller-supplied per-relation values keyed by
            ``relation.id``; a Decimal under ``copy`` aggregation or a tuple
            of Decimals under ``sum``.
        period: Optional period token; restricts active relations to those
            whose ``target_periods`` set contains it.
    """
    relations = tuple(_active_relations(revision, period=period))
    relation_ids = {relation.id for relation in relations}
    unknown = sorted(set(external_outputs).difference(relation_ids))
    if unknown:
        raise RegistryValidationError(f"unknown relation ids: {unknown!r}")
    resolved: dict[str, Decimal] = {}
    for relation in relations:
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


def resolve_relation_values_from_observations(
    revision: ModeloRevision,
    observations: Iterable[RegistryModeloObservation],
    *,
    filing_year: int,
    period: str,
) -> dict[str, Decimal]:
    """Resolve relation values from normalized filed-declaration observations.

    Args:
        revision: The :class:`ModeloRevision` whose relation declarations to resolve.
        observations: Filed-declaration :class:`RegistryModeloObservation`
            rows that supply the source values each relation consumes.
        filing_year: Target filing year; combined with each relation's source
            offset to match observation rows.
        period: Target period token whose relation requirements drive
            observation matching.
    """
    available = tuple(observations)
    external_outputs: dict[str, Decimal | tuple[Decimal, ...]] = {}
    for requirement in relation_source_requirements(revision, filing_year=filing_year, period=period):
        values = tuple(_observed_requirement_values(requirement, available))
        raw_value: Decimal | tuple[Decimal, ...]
        if requirement.aggregation_op == "copy":
            if len(values) != 1:
                raise RegistryValidationError(
                    f"relation requirement {requirement.relation_ids!r} copy aggregation requires one observation",
                )
            raw_value = values[0]
        else:
            raw_value = values
        for relation_id in requirement.relation_ids:
            external_outputs[relation_id] = raw_value
    return resolve_relation_values(revision, external_outputs, period=period)


def materialize_relation_binding_values(
    revision: ModeloRevision,
    relation_values: Mapping[str, Decimal],
    *,
    period: str | None = None,
) -> dict[str, Decimal]:
    """Copy resolved relation values into their declared target bindings.

    Relation ids remain the canonical formula-runtime keys. This helper is an
    additive bridge for registry rows that also declare ``target_binding`` so
    bound casillas can consume a relation-backed value without duplicating
    relation resolution in the application layer.

    Args:
        revision: The :class:`ModeloRevision` whose relation-to-binding
            mappings are used to populate the returned dict.
        relation_values: Already-resolved relation id to Decimal mapping.
        period: Optional period token; restricts active relations to those
            whose ``target_periods`` set contains it.
    """
    values: dict[str, Decimal] = {}
    for relation in _active_relations(revision, period=period):
        if relation.id not in relation_values:
            continue
        value = relation_values[relation.id]
        if isinstance(value, bool) or not isinstance(value, Decimal):
            raise RegistryValidationError(f"relation {relation.id!r} materialization requires a Decimal value")
        existing = values.get(relation.target_binding)
        if existing is not None and existing != value:
            raise RegistryValidationError(
                f"target binding {relation.target_binding!r} receives conflicting relation values",
            )
        values[relation.target_binding] = value
    return values


def _active_relations(revision: ModeloRevision, *, period: str | None) -> tuple[RelationDefinition, ...]:
    if period is None:
        return revision.relations
    return tuple(
        relation for relation in revision.relations if not relation.target_periods or period in relation.target_periods
    )


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


def _derive_offset_source_period(relation: RelationDefinition, *, target_period: str) -> str | None:
    anchor = _derive_offset_source_anchor(relation, target_period=target_period)
    return None if anchor is None else anchor[1]


def _derive_offset_source_anchor(relation: RelationDefinition, *, target_period: str) -> tuple[int, str] | None:
    """Apply ``source_period_offset_from_target`` to a target period code.

    Supports quarterly period codes (``1T``..``4T``), pago-fraccionado period
    codes used by modelo 202 (``1P``..``3P``), and zero-padded monthly codes
    (``01``..``12``). Delegates arithmetic to
    :func:`_period_offset_math.apply_period_offset`.
    """
    offset = relation.source_period_offset_from_target
    if offset is None:
        return None
    try:
        return apply_period_offset(offset, target_period=target_period)
    except RegistryValidationError as exc:
        raise RegistryValidationError(
            f"relation {relation.id!r} source_period_offset_from_target "
            f"cannot interpret target period {target_period!r}",
        ) from exc


def _observed_requirement_values(
    requirement: RegistryRelationSourceRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> tuple[Decimal, ...]:
    values: list[Decimal] = []
    for source_period in requirement.periods:
        matches = tuple(
            observation
            for observation in observations
            if observation.modelo == requirement.source_modelo
            and observation.filing_year == requirement.filing_year
            and observation.period == source_period
        )
        if len(matches) != 1:
            raise RegistryValidationError(
                f"relation requirement {requirement.relation_ids!r} expected one observed filing "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}, found {len(matches)}",
            )
        value = matches[0].casilla_values.get(requirement.source_output)
        if value is None:
            raise RegistryValidationError(
                f"relation requirement {requirement.relation_ids!r} requires observed output "
                f"{requirement.source_output!r} from "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}",
            )
        values.append(value)
    return tuple(values)
