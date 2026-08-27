"""One observation-fold helper for cross-filing fold-ins.

The single gather-and-fold primitive shared by both relation fold paths (the
application-layer relation prefill and the domain-layer
:func:`domain.calculations.registry.resolve_relation_values_from_observations`).
It matches the source filings a
:class:`~domain.calculations.registry.RegistryFoldRequirement` declares and
extracts the source casilla value per period, then folds the gathered values
through the requirement's declared ``copy`` / ``sum`` aggregation to one
:class:`~decimal.Decimal`.

Lives in the domain registry package (not the application source mesh) because
the domain relation resolver consumes it and the hexagonal direction forbids a
domain module importing the application layer.

See Also:
    :mod:`domain.calculations.registry._relations`
        Domain relation resolver that gathers and folds requirements here.
    :mod:`domain.calculations.registry._bindings_previous_filing`
        Previous-filing binding resolver that reuses :func:`fold_sum_or_copy`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from .errors import RegistryValidationError

if TYPE_CHECKING:
    from .bindings import RegistryModeloObservation
    from .relations import RegistryFoldRequirement


def gather_observed_requirement_values(
    requirement: RegistryFoldRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> tuple[Decimal, ...]:
    """Return the source-casilla values matched for one fold requirement, per period.

    Matches exactly one
    :class:`~domain.calculations.registry.RegistryModeloObservation` per
    declared source period and extracts the requirement's single source
    :class:`~core.CasillaId` value from each. The
    returned tuple carries one value per ``requirement.periods`` entry, in
    declaration order, ready for :func:`fold_observed_requirement_values`.
    """
    source_casilla_id = requirement.source_casilla_ids[0]
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
        value = matches[0].casilla_values.get(source_casilla_id)
        if value is None:
            raise RegistryValidationError(
                f"relation requirement {requirement.relation_ids!r} requires observed source casilla id "
                f"{source_casilla_id!r} from "
                f"{requirement.source_modelo!r}/{requirement.filing_year}/{source_period!r}",
            )
        values.append(value)
    return tuple(values)


def fold_sum_or_copy(
    op: str,
    values: tuple[Decimal, ...] | list[Decimal],
    *,
    subject: str,
    copy_unit: str,
) -> Decimal:
    """Fold a value sequence through the shared ``sum`` / ``copy`` arithmetic.

    The one place ``sum`` (add every value) and ``copy`` (require exactly one
    value and return it) are implemented. ``subject`` and ``copy_unit`` carry the
    caller's diagnostic vocabulary so a refused copy names the right entity
    (a relation requirement's observation, or a binding's source casilla). An op
    that is neither ``sum`` nor ``copy`` is rejected; callers handle any other op
    (e.g. the Modelo 130 ``prior_pagos_fraccionados`` identity) before delegating.

    Used by both :func:`fold_observed_requirement_values` and
    :func:`domain.calculations.registry.resolve_previous_filing_binding_values`.
    """
    if op == "copy":
        if len(values) != 1:
            raise RegistryValidationError(f"{subject} copy aggregation requires one {copy_unit}")
        return values[0]
    if op == "sum":
        return sum(values, Decimal("0"))
    raise RegistryValidationError(f"{subject} uses unsupported aggregation op {op!r}")


def fold_observed_requirement_values(
    requirement: RegistryFoldRequirement,
    values: tuple[Decimal, ...],
) -> Decimal:
    """Fold per-period source values through a requirement's ``copy`` / ``sum`` op.

    ``copy`` requires exactly one gathered value and returns it; ``sum`` adds the
    gathered values. This is the one fold both relation paths apply to a
    :class:`~domain.calculations.registry.RegistryFoldRequirement`; the
    period match is :func:`gather_observed_requirement_values`.
    """
    aggregation_op = requirement.aggregation_op
    # Every relation-derived requirement declares its aggregation op; only the
    # unrelated same-modelo previous_filing producer leaves it unset, and this
    # fold is the one both RELATION paths apply, per the docstring above.
    assert aggregation_op is not None
    return fold_sum_or_copy(
        aggregation_op,
        values,
        subject=f"relation requirement {requirement.relation_ids!r}",
        copy_unit="observation",
    )


def resolve_observed_requirement_value(
    requirement: RegistryFoldRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> Decimal:
    """Gather and fold one requirement to a single :class:`~decimal.Decimal`.

    Convenience wrapper for callers that already hold the normalized
    :class:`~domain.calculations.registry.RegistryModeloObservation` rows.
    """
    return fold_observed_requirement_values(
        requirement,
        gather_observed_requirement_values(requirement, observations),
    )
