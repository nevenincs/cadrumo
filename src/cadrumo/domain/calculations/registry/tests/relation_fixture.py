"""Compose canonical relation primitives for synthetic filed-observation fixtures."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from .....core.aggregation import RelationAggregationOp
from ..bindings import RegistryModeloObservation
from ..errors import RegistryValidationError
from ..ids import BindingId
from ..observation_fold import gather_observed_requirement_values
from ..relations import _fold_op, relation_prefill_bindings_for_period, relation_source_requirements
from ..schema import ModeloRevision


def resolve_relation_values_from_observations(
    revision: ModeloRevision,
    observations: Iterable[RegistryModeloObservation],
    *,
    filing_year: int,
    period: str,
) -> dict[BindingId, Decimal]:
    """Resolve relation-prefill values from normalized filed-declaration observations.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision` whose
            relation-prefill bindings to resolve.
        observations: Filed-declaration
            :class:`~cadrumo.domain.calculations.registry.bindings.RegistryModeloObservation`
            rows that supply the source values each fold consumes.
        filing_year: Target filing year; combined with each provider's temporal
            member to match observation rows.
        period: Target period token whose requirements drive observation
            matching.

    Returns:
        Resolved :class:`~cadrumo.domain.calculations.registry.ids.BindingId` values
        suitable for
        :func:`cadrumo.domain.calculations.registry.formula_runtime.calculate_registry_snapshot`.
    """
    available = tuple(observations)
    external_outputs: dict[BindingId, Decimal | tuple[Decimal, ...]] = {}
    for requirement in relation_source_requirements(revision, filing_year=filing_year, period=period):
        values = gather_observed_requirement_values(requirement, available)
        raw_value: Decimal | tuple[Decimal, ...]
        if requirement.aggregation_op == "copy":
            if len(values) != 1:
                raise RegistryValidationError(
                    f"fold requirement {requirement.target_bindings!r} copy aggregation requires one observation",
                )
            raw_value = values[0]
        else:
            raw_value = values
        for binding_id in requirement.target_bindings:
            external_outputs[binding_id] = raw_value
    return resolve_relation_values(revision, external_outputs, period=period)


def relation_prefill_values_as_binding_values(
    revision: ModeloRevision,
    values: Mapping[BindingId, Decimal],
    *,
    period: str | None = None,
) -> dict[BindingId, Decimal]:
    """Project resolved relation-prefill values onto their binding ids.

    Relation absorption makes the fold slot and its former target binding one
    declaration.  This small projection remains useful at boundaries that
    receive a pre-resolved map and need to merge it with ordinary binding
    inputs; it deliberately accepts only the active provider binding ids and
    never translates a retired relation id.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    active_ids = {binding.id for binding, _ in relation_prefill_bindings_for_period(revision, period=period)}
    unknown = sorted(set(values).difference(active_ids))
    if unknown:
        raise RegistryValidationError(f"unknown relation-prefill binding ids: {unknown!r}")
    return {binding_id: value for binding_id, value in values.items() if binding_id in active_ids}


def resolve_relation_values(
    revision: ModeloRevision,
    external_outputs: Mapping[BindingId, Decimal | tuple[Decimal, ...]],
    *,
    period: str | None = None,
) -> dict[BindingId, Decimal]:
    """Resolve relation-prefill values from caller-supplied external outputs.

    ``external_outputs`` is keyed by target binding id. ``copy`` folds one
    Decimal through unchanged; ``sum`` adds the tuple of matched per-period
    values.

    Args:
        revision: The
            :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision` whose
            relation-prefill bindings are resolved against the supplied outputs.
        external_outputs: Caller-supplied per-binding values keyed by
            :class:`~cadrumo.domain.calculations.registry.ids.BindingId`; a
            :class:`decimal.Decimal` under ``copy`` aggregation or a tuple of
            Decimals under ``sum``.
        period: Optional period token; restricts active bindings to those whose
            applicability admits it.
    """
    active = relation_prefill_bindings_for_period(revision, period=period)
    binding_ids = {binding.id for binding, _ in active}
    unknown = sorted(set(external_outputs).difference(binding_ids))
    if unknown:
        raise RegistryValidationError(f"unknown relation-prefill binding ids: {unknown!r}")
    resolved: dict[BindingId, Decimal] = {}
    for binding, _ in active:
        if binding.id not in external_outputs:
            raise RegistryValidationError(f"missing relation-prefill value for {binding.id!r}")
        raw_value = external_outputs[binding.id]
        if _fold_op(binding) is RelationAggregationOp.COPY:
            if not isinstance(raw_value, Decimal):
                raise RegistryValidationError(f"relation-prefill binding {binding.id!r} copy requires one Decimal")
            resolved[binding.id] = raw_value
        else:
            if not isinstance(raw_value, tuple):
                raise RegistryValidationError(
                    f"relation-prefill binding {binding.id!r} sum requires a tuple of Decimal values",
                )
            resolved[binding.id] = sum(raw_value, Decimal("0"))
    return resolved
