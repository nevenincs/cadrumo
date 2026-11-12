"""Which earlier periodo impositivo a Modelo 202 instalment takes its art. 40.2 base from.

LIS art. 40.2 bases the pago fraccionado on the cuota of the last periodo
impositivo whose declaration deadline had passed on the first day of the
instalment's payment window. The registry states that source once: the binding
:data:`MODELO_202_BASE_BINDING_ID` copies a Modelo 200 casilla with a filing-year
offset per instalment. Every consumer that needs the source of an instalment's
base resolves that binding through the canonical relation requirement resolver
here, so no consumer compares years or restates the offsets.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.relations import (
    RegistryFoldRequirement,
    relation_requirement_index,
    relation_source_requirements,
)
from .cross_period_models import period_strictly_before_activity_start

MODELO_202_BASE_BINDING_ID: Final[BindingId] = "modelo-202-cuota-base-ejercicio-anterior"
"""The binding that carries the art. 40.2 base of a Modelo 202 instalment from an earlier Modelo 200."""

_IS_INSTALMENT_ROLE: Final = "sociedades.instalment"


def modelo_202_form(*, operation: PinnedAuthorityOperation) -> str:
    """Return the form that holds the Impuesto sobre Sociedades instalment."""
    return form_for_role(_IS_INSTALMENT_ROLE, authority=operation)


def is_modelo_202(modelo: str, *, operation: PinnedAuthorityOperation) -> bool:
    """Return whether ``modelo`` is the form that holds the Impuesto sobre Sociedades instalment."""
    return modelo == modelo_202_form(operation=operation)


def modelo_202_base_source_requirement(
    instalment: Period,
    *,
    operation: PinnedAuthorityOperation,
) -> RegistryFoldRequirement | None:
    """Resolve the base binding of ``instalment`` to the earlier filing it reads.

    ``None`` when the edition that governs the instalment declares no base
    binding for its period, so the source is unknown rather than guessed.
    """
    snapshot = operation.reading_snapshot(
        modelo_202_form(operation=operation),
        filing_year=instalment.filing_year,
        period=instalment.registry_token,
    )
    requirements = relation_source_requirements(
        snapshot.revision,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
    )
    return relation_requirement_index(requirements).get(MODELO_202_BASE_BINDING_ID)


def modelo_202_base_source_periods(requirement: RegistryFoldRequirement) -> tuple[Period, ...]:
    """Return the earlier periods the base binding reads, as typed periods."""
    return tuple(Period.from_year_and_code(requirement.filing_year, token) for token in requirement.periods)


def modelo_202_instalment_has_no_prior_return(
    instalment: Period,
    *,
    activity_start_date: date | None,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return whether every period the instalment's base reads ended before the declared activity start.

    Such a periodo impositivo never existed for the entity, so no earlier
    return holds an art. 40.2 base and no ingreso results under it. The answer
    rests on the operator-declared activity start. It fails closed: without a
    declared start, or without a declared base binding, it is ``False``.
    """
    if activity_start_date is None:
        return False
    requirement = modelo_202_base_source_requirement(instalment, operation=operation)
    if requirement is None:
        return False
    return all(
        period_strictly_before_activity_start(period, activity_start_date)
        for period in modelo_202_base_source_periods(requirement)
    )


__all__ = [
    "MODELO_202_BASE_BINDING_ID",
    "is_modelo_202",
    "modelo_202_base_source_periods",
    "modelo_202_base_source_requirement",
    "modelo_202_form",
    "modelo_202_instalment_has_no_prior_return",
]
