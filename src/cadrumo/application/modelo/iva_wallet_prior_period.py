"""Prior-period IVA compensation evidence for the wallet gate."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple

from ...core.iva_compensation_provenance import IvaCompensationStateProvenance
from ...core.modelo import Modelo
from ...core.period import Period as _Period
from ...domain.calculations.registry.bindings_previous_filing import previous_filing_observation_requirements
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_AVAILABLE_CASILLA,
)
from ...domain.calculations.registry.relations import RegistryFoldRequirement
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ...domain.modelos.work_unit import WorkUnit
from ..calculations.binding_prefill import LocalIvaCompensationRecurrence
from ..calculations.iva_compensation_history_ports import IvaCompensationHistoryRepositoryProtocol
from ..calculations.m303_carry_ingress import M303CarryIngressError, validate_normalized_m303_carry_observation_envelope
from ..calculations.observations_repository import CalculationObservationRepositoryProtocol, ObservationEnvelopePayload
from ..calculations.revision_carry_gate import revision_carry_outcome

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

_M303_PRIOR_COMPENSATION_BINDING_ID = "modelo-303-compensacion-pendiente-anteriores"
_M303_AVAILABLE_COMPENSATION_CASILLA_ID = M303_COMPENSATION_AVAILABLE_CASILLA
_OPERATOR_DECLARED_PROVENANCES = frozenset(
    {IvaCompensationStateProvenance.OPERATOR_SEED, IvaCompensationStateProvenance.OPERATOR_CORRECTION}
)


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


_NO_PRIOR_PERIOD_OBSERVATION: Final = _PriorPeriodCarryEvidence(
    recurrence=None,
    prior_period_observation_found=False,
)


def _prior_period_observation_requirement(
    snapshot: RegistrySnapshot,
) -> RegistryFoldRequirement | None:
    requirements = tuple(
        requirement
        for requirement in previous_filing_observation_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        if requirement.source_modelo == Modelo("303").value
        and _M303_PRIOR_COMPENSATION_BINDING_ID in requirement.binding_ids
    )
    if len(requirements) != 1 or len(requirements[0].periods) != 1:
        return None
    return requirements[0]


def _prior_period_source_period(requirement: RegistryFoldRequirement) -> _Period:
    return (
        requirement.filing_periods[0]
        if requirement.filing_periods
        else _Period.from_year_and_code(requirement.filing_year, requirement.periods[0])
    )


def _prior_period_observation_is_usable(
    payload: ObservationEnvelopePayload,
    *,
    requirement: RegistryFoldRequirement,
    source_period: _Period,
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
    source_period: _Period,
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
    source_period: _Period,
) -> _PriorPeriodCarryEvidence:
    """Project an operator-declared opening balance into prior-period evidence.

    A seeded or corrected balance predates the local filed history, so no
    observation envelope exists for its period. It is local authority, never an
    AEAT observation; any other stored history state without its envelope is
    not usable and still proves the period existed.
    """
    if state is None:
        return _NO_PRIOR_PERIOD_OBSERVATION
    if state.provenance not in _OPERATOR_DECLARED_PROVENANCES:
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


def prior_period_carry_evidence(
    work_unit: WorkUnit,
    *,
    snapshot: RegistrySnapshot,
    operation: PinnedAuthorityOperation,
    repository: CalculationObservationRepositoryProtocol,
    history_repository: IvaCompensationHistoryRepositoryProtocol,
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

    Takes ``snapshot`` as a :class:`RegistrySnapshot`.
    """
    requirement = _prior_period_observation_requirement(snapshot)
    if requirement is None:
        return _NO_PRIOR_PERIOD_OBSERVATION
    source_period = _prior_period_source_period(requirement)
    payload = repository.load_observation(Modelo("303").value, source_period)
    if payload is None:
        return _operator_declared_carry_evidence(
            history_repository.load_period(source_period),
            requirement=requirement,
            source_period=source_period,
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
