"""One observation-fold helper for cross-filing fold-ins.

The single gather-and-fold primitive shared by both relation fold paths (the
application-layer relation prefill and the domain-layer
:func:`resolve_relation_values_from_observations`). It matches the source
filings a :class:`RegistryFoldRequirement` declares and extracts the source
casilla value per period, then folds the gathered values through the requirement's
declared ``copy`` / ``sum`` aggregation to one :class:`~decimal.Decimal`.

Lives in the domain registry package (not the application source mesh) because
the domain relation resolver consumes it and the hexagonal direction forbids a
domain module importing the application layer.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from ._errors import RegistryValidationError

if TYPE_CHECKING:
    from ._bindings import RegistryModeloObservation
    from ._relations import RegistryFoldRequirement


def gather_observed_requirement_values(
    requirement: RegistryFoldRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> tuple[Decimal, ...]:
    """Return the source-casilla values matched for one fold requirement, per period.

    Matches exactly one observed filing per declared source period (raising on a
    zero or multiple match), and extracts the requirement's single source casilla
    value from each. The returned tuple carries one value per ``requirement.periods``
    entry, in declaration order, ready for :func:`fold_observed_requirement_values`.
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
    gathered values. This is the one fold both relation paths apply; the period
    match is :func:`gather_observed_requirement_values`.
    """
    return fold_sum_or_copy(
        requirement.aggregation_op,
        values,
        subject=f"relation requirement {requirement.relation_ids!r}",
        copy_unit="observation",
    )


def resolve_observed_requirement_value(
    requirement: RegistryFoldRequirement,
    observations: tuple[RegistryModeloObservation, ...],
) -> Decimal:
    """Gather and fold one fold requirement to a single :class:`~decimal.Decimal`."""
    return fold_observed_requirement_values(
        requirement,
        gather_observed_requirement_values(requirement, observations),
    )
