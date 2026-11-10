"""Where each declaration an annual reconciliation sums stands, read once for the refusal and the to-do list.

An annual summary such as Modelo 390 reconciles boxes against the periodic
declarations of its year, whose figures it folds in from their filed values.
The registry declares those reconciliation relations and the source periods
each one reads; a source period whose filed values are not stored leaves the
summary unable to prove its reconciliation, so calculating it is refused.

This module answers, for each such source period, why its values are not there
yet: the declaration does not exist or has no calculation, its calculation is
not verified, or it is verified and not filed. The calculation's refusal names
the periods it needs from this answer, and the workbench's to-do list serves the
same answer before any calculation is tried, so both say the same thing. Each
need serves the step that puts it right: create the declaration when none exists,
or open it, where its own form says what it still lacks.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, StringConstraints

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.ids import RelationId
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue, CalculationRevisionState
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol
from ..calculations.relation_prefill import scoped_relation_source_requirements
from ..calculations.revision_carry_gate import revision_carry_outcome
from ..operations.next_step import OperationNextStepV1, OperationNextStepWording
from .calculation_modelo_adjustments import reconciliation_relation_targets
from .projection_next_steps import create_work_step, open_work_step
from .work_form_wording import modelo_number, period_words


class ReconciliationSourceStanding(StrEnum):
    """Why a source period's filed values are not stored yet."""

    MISSING = "missing"
    """No declaration exists for the period, or it has no calculation."""
    UNVERIFIED = "unverified"
    """The declaration is calculated and its calculation is not verified."""
    UNFILED = "unfiled"
    """The declaration is verified and not filed."""


_STANDING_LOCALE_KEYS: Final[dict[ReconciliationSourceStanding, str]] = {
    ReconciliationSourceStanding.MISSING: "application.modelo.reconciliation_sources.standing.missing",
    ReconciliationSourceStanding.UNVERIFIED: "application.modelo.reconciliation_sources.standing.unverified",
    ReconciliationSourceStanding.UNFILED: "application.modelo.reconciliation_sources.standing.unfiled",
}


@dataclass(frozen=True, slots=True)
class ReconciliationSourceNeed:
    """One source period the reconciliation needs, why it is not there yet, and its declaration if any."""

    modelo: str
    period: Period
    standing: ReconciliationSourceStanding
    unit: WorkUnit | None

    def words(self, language: OutputLanguage) -> str:
        """The period and its standing as one phrase in ``language``."""
        return tr(
            _STANDING_LOCALE_KEYS[self.standing],
            modelo=modelo_number(self.modelo, language),
            period=period_words(self.period, language),
            locale=language.value,
        )

    def next_step(self) -> OperationNextStepWording:
        """Create the declaration it lacks, or open it, where its own form says what is left.

        An existing declaration is opened even when it has no calculation, because
        its own form asks what calculating it needs first, such as the Modelo 303
        filing answers.
        """
        if self.unit is None:
            return create_work_step(modelo=self.modelo, period=self.period)
        return open_work_step(self.unit)


class ReconciliationSourceRequirementV1(BaseModel):
    """One source declaration the to-do list names before the summary can be worked out, and its door."""

    model_config = STRICT_FROZEN_CONFIG

    #: The period and why its filed figures are not there yet, in the form's language.
    words: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    #: Create or calculate that declaration, or open it.
    next_step: OperationNextStepV1


def reconciliation_source_requirements(
    needs: Iterable[ReconciliationSourceNeed], language: OutputLanguage
) -> tuple[ReconciliationSourceRequirementV1, ...]:
    """Word each need and its step in ``language``, keeping their order."""
    return tuple(
        ReconciliationSourceRequirementV1(words=need.words(language), next_step=need.next_step()(language))
        for need in needs
    )


def reconciliation_source_needs(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    observations: CalculationObservationRepositoryProtocol,
    activity_start_date: date | None,
    operation: PinnedAuthorityOperation,
    relation_ids: Iterable[RelationId] | None = None,
) -> tuple[ReconciliationSourceNeed, ...]:
    """The source periods of the snapshot's reconciliation relations whose filed values are not stored.

    ``relation_ids`` narrows the relations to those a refusal found unproven;
    without it every reconciliation relation the revision declares is read.
    Periods before the activity start owe no declaration and are not needed,
    as the fold itself scopes them out. Needs come in source-period order.
    """
    reconciliation = {relation_id for relation_id, *_rest in reconciliation_relation_targets(snapshot)}
    if relation_ids is not None:
        reconciliation &= set(relation_ids)
    if not reconciliation:
        return ()
    periods = _source_periods(snapshot, reconciliation, activity_start_date, operation=operation)
    needs: list[ReconciliationSourceNeed] = []
    for modelo, period in sorted(periods, key=lambda key: (key[0], key[1].filing_year, key[1].quarter_ordinal or 0)):
        if _filed_values_stored(modelo, period, observations=observations, operation=operation):
            continue
        unit = _declaration(modelo, period, bucket_id=bucket_id, work_catalogue=work_catalogue)
        standing = _standing(unit, calculation_catalogue)
        if standing is not None:
            needs.append(ReconciliationSourceNeed(modelo=modelo, period=period, standing=standing, unit=unit))
    return tuple(needs)


def _source_periods(
    snapshot: RegistrySnapshot,
    reconciliation: set[RelationId],
    activity_start_date: date | None,
    *,
    operation: PinnedAuthorityOperation,
) -> dict[tuple[str, Period], None]:
    """The distinct (source modelo, period) pairs the reconciliation relations read, in first-seen order."""
    periods: dict[tuple[str, Period], None] = {}
    for requirement in scoped_relation_source_requirements(snapshot, activity_start_date, operation=operation):
        if not reconciliation.intersection(requirement.target_bindings):
            continue
        for code in requirement.periods:
            periods[(str(requirement.source_modelo), Period.from_year_and_code(requirement.filing_year, code))] = None
    return periods


def _filed_values_stored(
    modelo: str,
    period: Period,
    *,
    observations: CalculationObservationRepositoryProtocol,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Whether the fold can read this period: a stored observation it would not drop as stale."""
    payload = observations.load_observation(modelo, period)
    return (
        payload is not None and not revision_carry_outcome(payload.registry_snapshot_ref, operation=operation).refused
    )


def _declaration(modelo: str, period: Period, *, bucket_id: str, work_catalogue: WorkUnitCatalogue) -> WorkUnit | None:
    for unit in work_catalogue.values():
        if (
            unit.bucket_id == bucket_id
            and str(unit.modelo) == modelo
            and unit.period == period
            and unit.state is WorkUnitState.BORRADOR
        ):
            return unit
    return None


def _standing(
    unit: WorkUnit | None, calculation_catalogue: CalculationRevisionCatalogue
) -> ReconciliationSourceStanding | None:
    """Why the declaration's filed values are absent; ``None`` when it is filed and only its values are missing."""
    head_id = None if unit is None else unit.current_calculation_revision_id
    head = None if head_id is None else calculation_catalogue.get(head_id)
    if head is None:
        return ReconciliationSourceStanding.MISSING
    if head.state is CalculationRevisionState.BORRADOR:
        return ReconciliationSourceStanding.UNVERIFIED
    if head.state is CalculationRevisionState.VERIFICADO_COMPLETO:
        return ReconciliationSourceStanding.UNFILED
    return None


__all__ = [
    "ReconciliationSourceNeed",
    "ReconciliationSourceRequirementV1",
    "ReconciliationSourceStanding",
    "reconciliation_source_needs",
    "reconciliation_source_requirements",
]
