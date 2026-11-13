"""Decide one Modelo 202 instalment's filing obligation below the LIS art. 40.3 threshold.

Orden HFP/227/2017 art. 1.3 makes the Modelo 202 owed below the threshold only in
an instalment where an ingreso results. Whether one results turns on the art. 40.3
election and, without it, on the art. 40.2 base, so the answer belongs to each
instalment rather than to the profile. An entity under the navieras tonelaje
regime has no election to read: LIS art. 116 imposes the art. 40.3 base, so its
instalment is decided by its own calculation, as an elected one is. The per-profile modality stays in the
domain; this module turns the facts one read gathered for an instalment into the
outcome the catalogue serves words for, and into the doors that move an undecided
instalment on. It reads nothing itself.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from ...core.period import Period
from ...domain.calculations.registry.applicability_modelo202 import (
    Modelo202BaseBasis,
    Modelo202InstalmentOutcome,
    Modelo202Modality,
    derive_modelo_202_modality,
    modelo_202_instalment_applicability,
    modelo_202_instalment_grounds,
)
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict, ModeloApplicability
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.result_casillas import canonical_result_amount, result_disposition_casilla_ids
from ...domain.deadlines.models import TaxpayerProfile
from ..calculations.modelo_202_base_source import is_modelo_202, modelo_202_form
from ..calculations.modelo_202_instalment_resolution import (
    Modelo202InstalmentBase,
    Modelo202InstalmentResolution,
    Modelo202InstalmentResolutionKind,
    Modelo202InstalmentUnresolvedReason,
)
from ..calculations.observations_repository import ObservationEnvelopePayload
from ..operator_actions.models import DeclaredNextAction
from .next_actions import declare_next_action

_CREATE_WORK_ACTION_ID: Final = "operator.modelo.work.create"
_CALCULATE_WORK_ACTION_ID: Final = "operator.modelo.work.calculate"
_CAPTURE_FILED_ACTION_ID: Final = "operator.live.filed.pull"
_VERIFY_WORK_ACTION_ID: Final = "operator.modelo.work.verify"
_PROFILE_EDIT_ACTION_ID: Final = "operator.profile.edit"
_DESCRIBE_ACTION_ID: Final = "operator.modelo.describe"
_BASE_DECIDED: Final = frozenset(
    {Modelo202InstalmentOutcome.BASE_POSITIVE, Modelo202InstalmentOutcome.BASE_NOT_POSITIVE}
)
#: The modalities under which filing turns on each instalment's ingreso.
_INGRESO_DECIDED_MODALITIES: Final = frozenset(
    {Modelo202Modality.ART_40_2_OPTIONAL, Modelo202Modality.ART_40_3_MANDATORY_REGIME}
)


@dataclass(frozen=True, slots=True)
class _CalculationOutcomes:
    """The outcomes an instalment decided by its own art. 40.3 calculation can reach."""

    pending_calculation: Modelo202InstalmentOutcome
    pending_verification: Modelo202InstalmentOutcome
    positive: Modelo202InstalmentOutcome
    zero: Modelo202InstalmentOutcome


_ELECTED: Final = _CalculationOutcomes(
    pending_calculation=Modelo202InstalmentOutcome.ELECTED_PENDING_CALCULATION,
    pending_verification=Modelo202InstalmentOutcome.ELECTED_PENDING_VERIFICATION,
    positive=Modelo202InstalmentOutcome.ELECTED_CALCULATION_POSITIVE,
    zero=Modelo202InstalmentOutcome.ELECTED_CALCULATION_ZERO,
)
_REGIME: Final = _CalculationOutcomes(
    pending_calculation=Modelo202InstalmentOutcome.REGIME_PENDING_CALCULATION,
    pending_verification=Modelo202InstalmentOutcome.REGIME_PENDING_VERIFICATION,
    positive=Modelo202InstalmentOutcome.REGIME_CALCULATION_POSITIVE,
    zero=Modelo202InstalmentOutcome.REGIME_CALCULATION_ZERO,
)
_PENDING_CALCULATION: Final = frozenset({_ELECTED.pending_calculation, _REGIME.pending_calculation})
_PENDING_VERIFICATION: Final = frozenset({_ELECTED.pending_verification, _REGIME.pending_verification})


@dataclass(frozen=True, slots=True)
class Modelo202BaseSource:
    """The earlier filing an instalment's base binding reads."""

    modelo: str
    period: Period


@dataclass(frozen=True, slots=True)
class Modelo202BaseReading:
    """The art. 40.2 base one instalment's binding resolved to, and the record it came from."""

    value: Decimal
    basis: Modelo202BaseBasis


@dataclass(frozen=True, slots=True)
class Modelo202CalculationReading:
    """The result of the instalment work unit's current calculation revision.

    Attributes:
        result: The canonical result amount of the revision.
        current: Whether the registry stamp of the work unit's current revision is
            the one the pinned authority selects and, where the revision anchored
            the ledger, no contributing ledger row has moved since.
        verified: Whether a passing verification sealed the revision; that
            verification ran the ledger and invoice drift gates when it sealed it.
    """

    result: Decimal
    current: bool
    verified: bool


@dataclass(frozen=True, slots=True)
class Modelo202InstalmentFacts:
    """Everything one read knows about one Modelo 202 instalment's ingreso.

    Attributes:
        instalment: The Modelo 202 period.
        election_stated: The art. 40.3 election in force at the start of the
            periodo impositivo: ``True`` elected, ``False`` stated not elected or
            renounced, ``None`` never stated.
        base_source: The earlier period the base binding reads, or ``None`` when
            the governing edition declares no base binding.
        no_prior_return: Whether every period the base binding reads ended before
            the declared activity start.
        base: The base the binding resolved to from a decisive record, if any.
        work_unit_id: The instalment's Modelo 202 work unit, if one exists.
        calculation: That work unit's current calculation, if any.
    """

    instalment: Period
    election_stated: bool | None
    base_source: Modelo202BaseSource | None
    no_prior_return: bool
    base: Modelo202BaseReading | None
    work_unit_id: str | None
    calculation: Modelo202CalculationReading | None


type Modelo202InstalmentFactsReader = Callable[[Period], Modelo202InstalmentFacts]
"""Gather one instalment's facts from the stores one read is bound to."""


@dataclass(frozen=True, slots=True)
class Modelo202InstalmentVerdict:
    """One instalment's filing verdict, the doors that move it on, and whether its election is unstated.

    Attributes:
        applicability: The verdict, unchanged where the instalment's facts are
            not consulted.
        doors: The primary door first, then its alternatives in order.
        election_unstated: Whether the verdict waits on the art. 40.3 election,
            a profile fact the calendar names as a gating key.
        decided_by_facts: Whether the instalment's own facts decided the
            verdict, rather than the profile alone.
    """

    applicability: ModeloApplicability
    doors: tuple[DeclaredNextAction, ...] = ()
    election_unstated: bool = False
    decided_by_facts: bool = False


def decide_modelo_202_instalment(
    facts: Modelo202InstalmentFacts, *, modality: Modelo202Modality
) -> Modelo202InstalmentOutcome:
    """Return the outcome the facts decide under ``modality``; an undecided instalment stays incomplete.

    Under the art. 40.3 method only the instalment's own calculation knows the
    base imponible of the 3, 9 or 11 months, and only a current calculation that
    a passing verification sealed shows it still answers the ledger and the
    invoices: its positive result decides an ingreso and its zero result none.
    The navieras tonelaje regime imposes that method (LIS art. 116); otherwise
    the declaración censal election chooses it. Without the election the
    art. 40.2 base decides, and a base that was never held stays incomplete
    rather than read as zero.
    """
    if modality is Modelo202Modality.ART_40_3_MANDATORY_REGIME:
        return _decide_from_calculation(facts.calculation, _REGIME)
    if facts.election_stated is None:
        return Modelo202InstalmentOutcome.ELECTION_UNSTATED
    if facts.election_stated:
        return _decide_from_calculation(facts.calculation, _ELECTED)
    return _decide_unelected_instalment(facts)


def _decide_from_calculation(
    calculation: Modelo202CalculationReading | None, outcomes: _CalculationOutcomes
) -> Modelo202InstalmentOutcome:
    """Decide an instalment under the art. 40.3 method from its own calculation."""
    if calculation is None or not calculation.current:
        return outcomes.pending_calculation
    if not calculation.verified:
        return outcomes.pending_verification
    if calculation.result > 0:
        return outcomes.positive
    return outcomes.zero


def _decide_unelected_instalment(facts: Modelo202InstalmentFacts) -> Modelo202InstalmentOutcome:
    """Decide an instalment without the election from the art. 40.2 base."""
    if facts.base_source is None:
        return Modelo202InstalmentOutcome.BASE_UNDECLARED
    if facts.no_prior_return:
        return Modelo202InstalmentOutcome.NO_PRIOR_RETURN
    if facts.base is None:
        return Modelo202InstalmentOutcome.BASE_ABSENT
    if facts.base.value > 0:
        return Modelo202InstalmentOutcome.BASE_POSITIVE
    return Modelo202InstalmentOutcome.BASE_NOT_POSITIVE


def _instalment_work_door(facts: Modelo202InstalmentFacts, *, modelo: str) -> DeclaredNextAction:
    """Calculate the instalment's work unit, or create it when none exists."""
    if facts.work_unit_id is not None:
        return declare_next_action(_CALCULATE_WORK_ACTION_ID, work_unit_id=facts.work_unit_id)
    return declare_next_action(
        _CREATE_WORK_ACTION_ID,
        modelo=modelo,
        year=facts.instalment.filing_year,
        period=facts.instalment.registry_token,
    )


def _base_absent_doors(
    facts: Modelo202InstalmentFacts,
    *,
    modelo: str,
    source: Modelo202BaseSource,
) -> tuple[DeclaredNextAction, ...]:
    """Hold the earlier Modelo 200 first; stating its cuota on the instalment is the alternative.

    The statement carries a figure only the operator supplies, so the calendar
    cannot serve it as a complete door. It opens the instalment's own
    verification instead, whose cross-period refusal offers the statement with
    that figure as its input; without a work unit it creates that unit first.
    """
    attest = (
        declare_next_action(_VERIFY_WORK_ACTION_ID, work_unit_id=facts.work_unit_id)
        if facts.work_unit_id is not None
        else _instalment_work_door(facts, modelo=modelo)
    )
    return (
        declare_next_action(
            _CREATE_WORK_ACTION_ID,
            modelo=source.modelo,
            year=source.period.filing_year,
            period=source.period.registry_token,
        ),
        declare_next_action(
            _CAPTURE_FILED_ACTION_ID,
            modelos=source.modelo,
            year=source.period.filing_year,
            period=source.period.registry_token,
        ),
        attest,
    )


def modelo_202_instalment_doors(
    outcome: Modelo202InstalmentOutcome,
    facts: Modelo202InstalmentFacts,
    *,
    modelo: str,
) -> tuple[DeclaredNextAction, ...]:
    """Return the doors of an outcome, the primary first, then its alternatives in order.

    An applicable or not-applicable outcome resting on recorded facts has none,
    except the no-prior-return outcome, which rests on the declared activity
    start and so opens the profile where that date is stated.
    """
    if outcome is Modelo202InstalmentOutcome.ELECTION_UNSTATED:
        return (declare_next_action(_PROFILE_EDIT_ACTION_ID),)
    if outcome in _PENDING_CALCULATION:
        return (_instalment_work_door(facts, modelo=modelo),)
    if outcome in _PENDING_VERIFICATION and facts.work_unit_id is not None:
        return (declare_next_action(_VERIFY_WORK_ACTION_ID, work_unit_id=facts.work_unit_id),)
    if outcome is Modelo202InstalmentOutcome.NO_PRIOR_RETURN:
        return (declare_next_action(_PROFILE_EDIT_ACTION_ID),)
    if outcome is Modelo202InstalmentOutcome.BASE_UNDECLARED:
        return (declare_next_action(_DESCRIBE_ACTION_ID, modelo=modelo),)
    if outcome is Modelo202InstalmentOutcome.BASE_ABSENT and facts.base_source is not None:
        return _base_absent_doors(facts, modelo=modelo, source=facts.base_source)
    return ()


def modelo_202_instalment_verdict(
    applicability: ModeloApplicability,
    *,
    instalment: Period,
    profile: TaxpayerProfile,
    facts_reader: Modelo202InstalmentFactsReader,
    operation: PinnedAuthorityOperation,
) -> Modelo202InstalmentVerdict:
    """Decide one Modelo 202 instalment where the profile alone left the obligation open.

    Only an incomplete Modelo 202 verdict below the threshold is decided here,
    under modalidad cuota or the navieras tonelaje regime: every other verdict,
    including the incomplete one of an undeclared INCN and the applicable one
    above the threshold, passes through unchanged.
    """
    if applicability.verdict is not ApplicabilityVerdict.INCOMPLETE or not is_modelo_202(
        str(applicability.modelo), operation=operation
    ):
        return Modelo202InstalmentVerdict(applicability)
    effective_date = date(instalment.filing_year, 12, 31)
    modality = derive_modelo_202_modality(profile, effective_date=effective_date, authority=operation)
    if modality.modality not in _INGRESO_DECIDED_MODALITIES:
        return Modelo202InstalmentVerdict(applicability)
    facts = facts_reader(instalment)
    outcome = decide_modelo_202_instalment(facts, modality=modality.modality)
    basis = _decided_basis(facts, outcome)
    decided = modelo_202_instalment_applicability(
        applicability,
        outcome,
        basis=basis,
        effective_date=effective_date,
        authority=operation,
    )
    return Modelo202InstalmentVerdict(
        applicability=decided,
        doors=modelo_202_instalment_doors(outcome, facts, modelo=str(applicability.modelo)),
        election_unstated=outcome is Modelo202InstalmentOutcome.ELECTION_UNSTATED,
        decided_by_facts=True,
    )


def _decided_basis(facts: Modelo202InstalmentFacts, outcome: Modelo202InstalmentOutcome) -> Modelo202BaseBasis | None:
    """Name the record that supplied the base, where the base decided the outcome."""
    return facts.base.basis if facts.base is not None and outcome in _BASE_DECIDED else None


def _filed_amount(filing: ObservationEnvelopePayload, *, operation: PinnedAuthorityOperation) -> Decimal | None:
    """Return the filed instalment's canonical result, or ``None`` where the form declares none."""
    modelo = modelo_202_form(operation=operation)
    result_ids = result_disposition_casilla_ids(modelo)
    if result_ids is None:
        return None
    observed = filing.observation.casilla_values
    return canonical_result_amount(
        modelo, {casilla_id: observed[casilla_id] for casilla_id in result_ids if casilla_id in observed}
    )


def resolve_modelo_202_instalment(
    facts: Modelo202InstalmentFacts,
    *,
    filing: ObservationEnvelopePayload | None,
    modality: Modelo202Modality | None,
    operation: PinnedAuthorityOperation,
) -> Modelo202InstalmentResolution:
    """Resolve what one instalment contributes to the settlement of its ejercicio.

    ``filing`` is the presented filing of the instalment, if one is held: its
    local filing or captured AEAT evidence, never a draft or an operator entry.
    A held filing is folded as filed whatever the verdict says. Without one the
    instalment counts as nothing paid only when its own verdict, decided by
    :func:`decide_modelo_202_instalment` below the art. 40.3 threshold, says no
    Modelo 202 was owed (Orden HFP/227/2017 art. 1.3: below that threshold the
    declaration is presented only where an ingreso results, for a naviera as
    for any other sociedad). Above the threshold
    every instalment is owed, and a modality that could not be derived or a
    verdict still incomplete leaves the instalment unresolved, never zero.
    """
    instalment = facts.instalment
    if filing is not None:
        return Modelo202InstalmentResolution(
            instalment=instalment,
            kind=Modelo202InstalmentResolutionKind.FILED,
            amount=_filed_amount(filing, operation=operation),
            filing=filing,
        )
    if modality is Modelo202Modality.ART_40_3_MANDATORY:
        return Modelo202InstalmentResolution(
            instalment=instalment,
            kind=Modelo202InstalmentResolutionKind.UNRESOLVED,
            unresolved_reason=Modelo202InstalmentUnresolvedReason.OWED_UNFILED,
        )
    if modality not in _INGRESO_DECIDED_MODALITIES:
        return Modelo202InstalmentResolution(
            instalment=instalment,
            kind=Modelo202InstalmentResolutionKind.UNRESOLVED,
            unresolved_reason=Modelo202InstalmentUnresolvedReason.VERDICT_UNDECIDED,
        )
    outcome = decide_modelo_202_instalment(facts, modality=modality)
    basis = _decided_basis(facts, outcome)
    grounds = modelo_202_instalment_grounds(
        outcome,
        basis=basis,
        effective_date=date(instalment.filing_year, 12, 31),
        authority=operation,
    )
    base = (
        None
        if basis is None or facts.base is None or facts.base_source is None
        else Modelo202InstalmentBase(
            value=facts.base.value,
            basis=basis,
            source_modelo=facts.base_source.modelo,
            source_period=facts.base_source.period,
        )
    )
    if outcome.verdict is ApplicabilityVerdict.NOT_APPLICABLE:
        return Modelo202InstalmentResolution(
            instalment=instalment,
            kind=Modelo202InstalmentResolutionKind.NOT_OWED,
            amount=Decimal("0.00"),
            grounds=grounds,
            base=base,
        )
    return Modelo202InstalmentResolution(
        instalment=instalment,
        kind=Modelo202InstalmentResolutionKind.UNRESOLVED,
        grounds=grounds,
        base=base,
        unresolved_reason=(
            Modelo202InstalmentUnresolvedReason.OWED_UNFILED
            if outcome.verdict is ApplicabilityVerdict.APPLICABLE
            else Modelo202InstalmentUnresolvedReason.VERDICT_UNDECIDED
        ),
    )


__all__ = [
    "Modelo202BaseReading",
    "Modelo202BaseSource",
    "Modelo202CalculationReading",
    "Modelo202InstalmentFacts",
    "Modelo202InstalmentFactsReader",
    "Modelo202InstalmentVerdict",
    "decide_modelo_202_instalment",
    "modelo_202_instalment_doors",
    "modelo_202_instalment_verdict",
    "resolve_modelo_202_instalment",
]
