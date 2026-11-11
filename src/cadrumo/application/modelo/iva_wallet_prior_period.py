"""Prior-period IVA compensation evidence for the wallet gate.

Core types: :class:`~cadrumo.domain.modelos.calculation_revision.CalculationRevision`.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Final, NamedTuple, Protocol

from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
)
from ...domain.calculations.registry.relations import RegistryFoldRequirement
from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
from ...domain.iva.refund_eligibility import (
    RefundEligibilityOutcome,
    redeme_enrolment_state,
    refund_eligibility_for_period,
)
from ...domain.iva_compensation.carry_forward import OPERATOR_DECLARED_PROVENANCES, IvaCompensationPeriodState
from ...domain.iva_compensation.reconciliation import LOCAL_CALCULATION_SOURCE_KIND, IvaCompensationDecisionReason
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionState
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ..calculations.binding_prefill import LocalIvaCompensationRecurrence
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.m303_carry_ingress import M303CarryIngressError, validate_normalized_m303_carry_observation_envelope
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol, ObservationEnvelopePayload
from ..calculations.revision_carry_gate import revision_carry_outcome
from ..user_profile.projections import declared_redeme_enrolment

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol

_M303_PRIOR_COMPENSATION_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"
_M303_AVAILABLE_COMPENSATION_CASILLA_ID = M303_COMPENSATION_AVAILABLE_CASILLA


class _PriorPeriodCarryEvidence(NamedTuple):
    """What the wallet gate learned about the prior Modelo 303 period.

    ``recurrence`` is the usable carry projection, or ``None`` when this build
    cannot turn the stored observation into one.
    ``prior_period_observation_found`` answers the separate question of whether
    an observation for that period was persisted at all. An observation that
    exists but cannot be used still proves the period existed, so only a genuine
    absence may ground a first-period zero on the compensación.
    """

    recurrence: LocalIvaCompensationRecurrence | None
    prior_period_observation_found: bool
    local_calculation_refusal: IvaCompensationDecisionReason | None = None


class PriorModeloCalculations(Protocol):
    """The taxpayer's own calculations of earlier periods, read where nothing filed records one."""

    def latest_revision(self, modelo: str, period: Period) -> CalculationRevision | None:
        """Return the newest live calculation revision of ``modelo`` for ``period``, or ``None``."""
        ...


_DEAD_REVISION_STATES: Final = frozenset(
    {CalculationRevisionState.DESCARTADO, CalculationRevisionState.PRESENTADO_SUPERSEDIDO}
)


class CataloguePriorModeloCalculations:
    """:class:`PriorModeloCalculations` over the bucket's work and calculation catalogues.

    The calculation catalogue is read once, and only when a prior period has a
    work unit to look up.
    """

    def __init__(
        self,
        *,
        work_units: WorkUnitCatalogue,
        calculation_repository: CalculationRevisionCatalogueRepositoryProtocol,
        operation: PinnedAuthorityOperation,
    ) -> None:
        """Read ``work_units`` as loaded and the calculations through ``calculation_repository`` on demand."""
        self._work_units = work_units
        self._calculation_repository = calculation_repository
        self._operation = operation
        self._revisions: dict[str, tuple[CalculationRevision, ...]] | None = None

    def latest_revision(self, modelo: str, period: Period) -> CalculationRevision | None:
        """Return the newest live calculation revision of ``modelo`` for ``period``, or ``None``."""
        unit_ids = tuple(
            unit.work_unit_id
            for unit in self._work_units
            if unit.modelo == modelo and unit.period == period and unit.state is not WorkUnitState.DESCARTADO
        )
        if not unit_ids:
            return None
        revisions = self._revisions_by_work_unit()
        live = tuple(
            revision
            for unit_id in unit_ids
            for revision in revisions.get(unit_id, ())
            if revision.state not in _DEAD_REVISION_STATES
        )
        if not live:
            return None
        return max(live, key=lambda revision: (revision.created_at, revision.calculation_revision_id))

    def _revisions_by_work_unit(self) -> dict[str, tuple[CalculationRevision, ...]]:
        if self._revisions is None:
            grouped: dict[str, list[CalculationRevision]] = {}
            for revision in self._calculation_repository.load(operation=self._operation):
                grouped.setdefault(revision.work_unit_id, []).append(revision)
            self._revisions = {unit_id: tuple(revisions) for unit_id, revisions in grouped.items()}
        return self._revisions


_NO_PRIOR_PERIOD_OBSERVATION: Final = _PriorPeriodCarryEvidence(
    recurrence=None,
    prior_period_observation_found=False,
)


def _prior_period_observation_requirement(
    snapshot: RegistrySnapshot,
) -> RegistryFoldRequirement | None:
    return _prior_compensation_requirement(snapshot.revision, filing_year=snapshot.filing_year, period=snapshot.period)


def _prior_compensation_requirement(
    revision: ModeloRevision, *, filing_year: int, period: str
) -> RegistryFoldRequirement | None:
    requirements = tuple(
        requirement
        for requirement in previous_filing_observation_requirements(
            revision,
            filing_year=filing_year,
            period=period,
        )
        if requirement.source_modelo == form_for_role("iva.periodic")
        and _M303_PRIOR_COMPENSATION_BINDING_ID in requirement.binding_ids
    )
    if len(requirements) != 1 or len(requirements[0].periods) != 1:
        return None
    return requirements[0]


def _prior_period_source_period(requirement: RegistryFoldRequirement) -> Period:
    return (
        requirement.filing_periods[0]
        if requirement.filing_periods
        else Period.from_year_and_code(requirement.filing_year, requirement.periods[0])
    )


def prior_compensation_source_period(revision: ModeloRevision, carry_period: Period) -> Period | None:
    """The Modelo 303 period whose closing balance ``carry_period``'s prior compensation reads.

    It is the period an opening balance is declared for, since a period's
    declared balance is the one the period after it carries; ``revision`` is the
    edition calculating ``carry_period``, whose own requirement names it.
    ``None`` when the revision reads no single earlier period for it.
    """
    requirement = _prior_compensation_requirement(
        revision, filing_year=carry_period.filing_year, period=carry_period.registry_token
    )
    return None if requirement is None else _prior_period_source_period(requirement)


def _prior_period_observation_is_usable(
    payload: ObservationEnvelopePayload,
    *,
    requirement: RegistryFoldRequirement,
    source_period: Period,
    operation: PinnedAuthorityOperation,
) -> bool:
    observation = payload.observation
    return (
        observation.filing_year == requirement.filing_year
        and observation.period == source_period.registry_token
        and not revision_carry_outcome(payload.registry_snapshot_ref, operation=operation).refused
    )


def _validated_prior_period_observation(
    payload: ObservationEnvelopePayload,
    *,
    operation: PinnedAuthorityOperation,
) -> ObservationEnvelopePayload | None:
    try:
        return validate_normalized_m303_carry_observation_envelope(payload, operation=operation)
    except M303CarryIngressError:
        return None


def _prior_period_recurrence(
    payload: ObservationEnvelopePayload,
    *,
    requirement: RegistryFoldRequirement,
    source_period: Period,
) -> LocalIvaCompensationRecurrence | None:
    amount = payload.observation.casilla_values.get(_M303_AVAILABLE_COMPENSATION_CASILLA_ID)
    if amount is None:
        return None
    return LocalIvaCompensationRecurrence(
        binding_id=_M303_PRIOR_COMPENSATION_BINDING_ID,
        amount=amount,
        source_kind=str(payload.source_kind),
        source_modelo=Modelo("303").value,
        source_filing_year=requirement.filing_year,
        source_periods=(source_period,),
        source_registry_snapshot_refs=(payload.registry_snapshot_ref,),
        resolved_at=payload.captured_at,
        source_locator=(
            f"observation-envelope:{Modelo('303').value}:{source_period.filing_year}:{source_period.registry_token}"
        ),
    )


def _operator_declared_carry_evidence(
    state: IvaCompensationPeriodState | None,
    *,
    requirement: RegistryFoldRequirement,
    source_period: Period,
) -> _PriorPeriodCarryEvidence:
    """Project an operator-declared opening balance into prior-period evidence.

    A seeded or corrected balance predates the local filed history, so no
    observation envelope exists for its period. It is local authority, never an
    AEAT observation; any other stored history state without its envelope is
    not usable and still proves the period existed.
    """
    if state is None:
        return _NO_PRIOR_PERIOD_OBSERVATION
    if state.provenance not in OPERATOR_DECLARED_PROVENANCES:
        return _PriorPeriodCarryEvidence(recurrence=None, prior_period_observation_found=True)
    return _PriorPeriodCarryEvidence(
        recurrence=LocalIvaCompensationRecurrence(
            binding_id=_M303_PRIOR_COMPENSATION_BINDING_ID,
            amount=state.available_end_amount,
            source_kind=state.provenance.value,
            source_modelo=Modelo("303").value,
            source_filing_year=requirement.filing_year,
            source_periods=(source_period,),
            source_registry_snapshot_refs=(state.registry_snapshot_ref,),
            resolved_at=state.presented_at,
            source_locator=(
                f"iva-compensation-history:{Modelo('303').value}:"
                f"{source_period.filing_year}:{source_period.registry_token}"
            ),
        ),
        prior_period_observation_found=True,
    )


def _local_calculation_refusal(
    amount: Decimal,
    *,
    source_period: Period,
    profile_values: Mapping[str, str] | None,
) -> IvaCompensationDecisionReason | None:
    """Why a calculated credit of ``source_period`` cannot be carried, or ``None`` where the law leaves only carrying.

    LIVA art. 115 carries the credit in full only outside the year's last
    period and outside REDEME. Elsewhere the unfiled calculation has not made
    the choice between refund and compensation the law leaves open.
    """
    if amount <= 0:
        return None
    eligibility = refund_eligibility_for_period(
        period=source_period,
        redeme=redeme_enrolment_state(declared_redeme_enrolment(profile_values)),
    )
    if eligibility.outcome is RefundEligibilityOutcome.CARRY_FORWARD_ONLY:
        return None
    if eligibility.outcome is RefundEligibilityOutcome.UNDETERMINED_REDEME_UNSTATED:
        return IvaCompensationDecisionReason.LOCAL_CALCULATION_REDEME_UNSTATED
    return IvaCompensationDecisionReason.LOCAL_CALCULATION_REFUND_UNDECIDED


def _local_calculation_carry_evidence(
    prior_calculations: PriorModeloCalculations | None,
    *,
    requirement: RegistryFoldRequirement,
    source_period: Period,
    profile_values: Mapping[str, str] | None,
) -> _PriorPeriodCarryEvidence:
    """Project the taxpayer's calculation of ``source_period`` into evidence where nothing filed records it.

    The carried amount is that calculation's compensación disponible a final de
    periodo. It is a local calculation, never AEAT's wallet or a filed return,
    so it feeds the next period at calculation grade only.
    """
    if prior_calculations is None:
        return _NO_PRIOR_PERIOD_OBSERVATION
    modelo = form_for_role("iva.periodic")
    revision = prior_calculations.latest_revision(modelo, source_period)
    if revision is None:
        return _NO_PRIOR_PERIOD_OBSERVATION
    amount = revision.casilla_values.get(_M303_AVAILABLE_COMPENSATION_CASILLA_ID)
    if amount is None:
        return _PriorPeriodCarryEvidence(recurrence=None, prior_period_observation_found=True)
    return _PriorPeriodCarryEvidence(
        recurrence=LocalIvaCompensationRecurrence(
            binding_id=_M303_PRIOR_COMPENSATION_BINDING_ID,
            amount=amount,
            source_kind=LOCAL_CALCULATION_SOURCE_KIND,
            source_modelo=modelo,
            source_filing_year=requirement.filing_year,
            source_periods=(source_period,),
            source_registry_snapshot_refs=(revision.registry_snapshot_ref,),
            resolved_at=revision.updated_at,
            source_locator=(
                f"calculation-revision:{modelo}:{source_period.filing_year}:"
                f"{source_period.registry_token}:{revision.calculation_revision_id}"
            ),
        ),
        prior_period_observation_found=True,
        local_calculation_refusal=_local_calculation_refusal(
            amount, source_period=source_period, profile_values=profile_values
        ),
    )


def prior_period_carry_evidence(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
    prior_calculations: PriorModeloCalculations | None = None,
    profile_values: Mapping[str, str] | None = None,
) -> _PriorPeriodCarryEvidence:
    """Return validated filed M303 envelope recurrence, and whether one was stored.

    A prior calculation revision records a local calculation, not the filed
    declaration's disposition. It therefore cannot establish this recurrence.
    Missing, unnormalized, revision-refused, or disposition-conflicting envelopes
    yield no usable recurrence, so the wallet gate blocks rather than selecting
    an invented carry amount.

    Every case that found a stored observation and could not use it additionally
    reports it as present. Previously all of them returned a bare ``None``
    indistinguishable from a genuine absence, and the caller paired that ``None``
    with the profile's activity-start proof to reach ``first_period_zero`` -- so
    an envelope this build could not read was converted into a proven zero on the
    compensación, laundering a taxpayer's carried credit into nothing. The
    docstring claimed the gate blocked in those cases, which was true of every
    path except the one that mattered.

    Where neither a filed observation nor a declared opening balance records
    the prior period, ``prior_calculations`` supplies the taxpayer's own
    calculation of it at calculation grade, and ``profile_values`` answers the
    REDEME question that decides whether its credit may be carried.

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    requirement = _prior_period_observation_requirement(snapshot)
    if requirement is None:
        return _NO_PRIOR_PERIOD_OBSERVATION
    source_period = _prior_period_source_period(requirement)
    payload = repository.load_observation(Modelo("303").value, source_period)
    if payload is None:
        declared = _operator_declared_carry_evidence(
            history_repository.load_period(source_period),
            requirement=requirement,
            source_period=source_period,
        )
        if declared.prior_period_observation_found:
            return declared
        return _local_calculation_carry_evidence(
            prior_calculations,
            requirement=requirement,
            source_period=source_period,
            profile_values=profile_values,
        )
    found = _PriorPeriodCarryEvidence(recurrence=None, prior_period_observation_found=True)
    if not _prior_period_observation_is_usable(
        payload,
        requirement=requirement,
        source_period=source_period,
        operation=operation,
    ):
        return found
    validated = _validated_prior_period_observation(payload, operation=operation)
    if validated is None:
        return found
    recurrence = _prior_period_recurrence(
        validated,
        requirement=requirement,
        source_period=source_period,
    )
    if recurrence is None:
        return found
    return _PriorPeriodCarryEvidence(
        recurrence=recurrence,
        prior_period_observation_found=True,
    )
