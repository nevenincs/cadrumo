"""Modelo 202 instalments of an entity under the navieras tonelaje regime.

LIS art. 116 obliges such an entity to the art. 40.3 base, whatever its
declaración censal says, so its instalment is decided by its own calculation.
Orden HFP/227/2017 art. 1.3 still makes the Modelo 202 owed in every instalment
only above the art. 40.3 turnover threshold; below it, only where an ingreso
results. These tests drive the real calendar and the real settlement resolver.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.applicability_modelo202 import (
    Modelo202InstalmentOutcome,
    Modelo202Modality,
    derive_modelo_202_modality,
    modelo_202_incn_threshold_decimal,
    modelo_202_instalment_grounds,
    resolve_modelo_202_art_40_3_incn_threshold,
)
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.entity_type import EntityType
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile
from ...calculations.modelo_202_instalment_resolution import (
    Modelo202InstalmentResolutionKind,
    Modelo202InstalmentUnresolvedReason,
)
from ..applicability_evidence import FilingYearApplicabilityEvidence
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendar, OverviewCalendarRange
from ..modelo202_instalment import (
    Modelo202CalculationReading,
    Modelo202InstalmentFacts,
    decide_modelo_202_instalment,
    resolve_modelo_202_instalment,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_202 = "202"
_INSTALMENTS = ("1P", "2P", "3P")
_WORK_UNIT_ID = "b" * 64
_ELECTION_SELECTOR = "taxpayer.pago_fraccionado_art_40_3_elected"
_REGIME = Modelo202Modality.ART_40_3_MANDATORY_REGIME
_POSITIVE = Modelo202CalculationReading(result=Decimal("250.00"), current=True, verified=True)
_ZERO = Modelo202CalculationReading(result=Decimal("0"), current=True, verified=True)
_UNVERIFIED = Modelo202CalculationReading(result=Decimal("250.00"), current=True, verified=False)
_STALE = Modelo202CalculationReading(result=Decimal("0"), current=False, verified=True)


def _year() -> int:
    return filing_year_envelope().horizon


def _facts(token: str, calculation: Modelo202CalculationReading | None) -> Modelo202InstalmentFacts:
    """A naviera's instalment with no art. 40.3 election stated: the law, not the election, sets the method."""
    return Modelo202InstalmentFacts(
        instalment=Period.from_year_and_code(_year(), token),
        election_stated=None,
        base_source=None,
        no_prior_return=False,
        base=None,
        work_unit_id=_WORK_UNIT_ID if calculation is not None else None,
        calculation=calculation,
    )


def _threshold(operation: PinnedAuthorityOperation) -> Decimal:
    return modelo_202_incn_threshold_decimal(
        resolve_modelo_202_art_40_3_incn_threshold(effective_date=date(_year(), 12, 31), authority=operation),
    )


def _naviera(turnover: Decimal) -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_professionals_with_retencion=False,
        art109_activity_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
        enrollment=ModeloEnrollment(large_company=False),
        incn_prior_12_months=turnover,
        regimen_entidades_navieras_tonelaje=True,
    )


def _calendar(
    profile: TaxpayerProfile,
    facts_for: dict[str, Modelo202InstalmentFacts] | None,
    operation: PinnedAuthorityOperation,
) -> OverviewCalendar:
    def read(instalment: Period) -> Modelo202InstalmentFacts:
        if facts_for is None:
            raise AssertionError("above the threshold no instalment fact is consulted")
        return facts_for[instalment.registry_token]

    evidence = FilingYearApplicabilityEvidence(
        profile_for_year=lambda _year: profile,
        ledger_payer_facts_for_year=lambda _year: {},
        modelo_202_instalment_facts=read,
    )
    year = _year()
    return build_overview_calendar(
        profile,
        OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year, 12, 31)),
        operation=operation,
        today=date(year, 1, 1),
        show_suppressed=True,
        applicability_evidence=evidence,
    )


@pytest.mark.parametrize(
    ("calculation", "expected"),
    [
        (None, Modelo202InstalmentOutcome.REGIME_PENDING_CALCULATION),
        (_STALE, Modelo202InstalmentOutcome.REGIME_PENDING_CALCULATION),
        (_UNVERIFIED, Modelo202InstalmentOutcome.REGIME_PENDING_VERIFICATION),
        (_POSITIVE, Modelo202InstalmentOutcome.REGIME_CALCULATION_POSITIVE),
        (_ZERO, Modelo202InstalmentOutcome.REGIME_CALCULATION_ZERO),
    ],
)
def test_the_regime_decides_from_the_calculation_whatever_the_election(
    calculation: Modelo202CalculationReading | None, expected: Modelo202InstalmentOutcome
) -> None:
    """An unstated election never holds a naviera's instalment: LIS art. 116 already chose the method."""
    assert decide_modelo_202_instalment(_facts("2P", calculation), modality=_REGIME) is expected


def test_a_naviera_below_the_threshold_owes_only_the_instalments_with_an_ingreso(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    facts = {"1P": _facts("1P", _POSITIVE), "2P": _facts("2P", _ZERO), "3P": _facts("3P", None)}
    calendar = _calendar(_naviera(_threshold(authority_operation)), facts, authority_operation)

    surfaced = {entry.period.registry_token for entry in calendar.entries if entry.modelo == _MODELO_202}
    suppressed = {
        entry.period.registry_token: entry for entry in calendar.suppressed_entries if entry.modelo == _MODELO_202
    }
    assert surfaced == {"1P"}
    assert suppressed["2P"].verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert suppressed["2P"].actions == ()
    assert suppressed["3P"].verdict is ApplicabilityVerdict.INCOMPLETE
    assert [door.action.action_id for door in suppressed["3P"].actions] == ["operator.modelo.work.create"]
    assert "navieras" in suppressed["2P"].reason
    assert "navieras" in suppressed["3P"].reason
    assert [warning for warning in calendar.warnings if warning.code == _ELECTION_SELECTOR] == []


def test_a_naviera_above_the_threshold_owes_every_instalment(authority_operation: PinnedAuthorityOperation) -> None:
    calendar = _calendar(_naviera(_threshold(authority_operation) + Decimal("0.01")), None, authority_operation)

    surfaced = {entry.period.registry_token for entry in calendar.entries if entry.modelo == _MODELO_202}
    assert surfaced == set(_INSTALMENTS)


def test_the_regime_outcomes_never_speak_of_an_election(authority_operation: PinnedAuthorityOperation) -> None:
    """The regime is a legal obligation, so its served words are its own, not the election's."""
    effective_date = date(_year(), 12, 31)
    pairs = (
        (Modelo202InstalmentOutcome.REGIME_PENDING_CALCULATION, Modelo202InstalmentOutcome.ELECTED_PENDING_CALCULATION),
        (
            Modelo202InstalmentOutcome.REGIME_PENDING_VERIFICATION,
            Modelo202InstalmentOutcome.ELECTED_PENDING_VERIFICATION,
        ),
        (
            Modelo202InstalmentOutcome.REGIME_CALCULATION_POSITIVE,
            Modelo202InstalmentOutcome.ELECTED_CALCULATION_POSITIVE,
        ),
        (Modelo202InstalmentOutcome.REGIME_CALCULATION_ZERO, Modelo202InstalmentOutcome.ELECTED_CALCULATION_ZERO),
    )
    for regime, elected in pairs:
        regime_reason = modelo_202_instalment_grounds(
            regime, basis=None, effective_date=effective_date, authority=authority_operation
        ).reason
        elected_reason = modelo_202_instalment_grounds(
            elected, basis=None, effective_date=effective_date, authority=authority_operation
        ).reason
        assert regime.verdict is elected.verdict, regime
        assert "navieras" in regime_reason, regime
        assert "opción" not in regime_reason, regime
        assert regime_reason != elected_reason, regime


@pytest.mark.parametrize(
    ("calculation", "kind", "unresolved_reason"),
    [
        (_ZERO, Modelo202InstalmentResolutionKind.NOT_OWED, None),
        (_POSITIVE, Modelo202InstalmentResolutionKind.UNRESOLVED, Modelo202InstalmentUnresolvedReason.OWED_UNFILED),
        (
            _UNVERIFIED,
            Modelo202InstalmentResolutionKind.UNRESOLVED,
            Modelo202InstalmentUnresolvedReason.VERDICT_UNDECIDED,
        ),
        (None, Modelo202InstalmentResolutionKind.UNRESOLVED, Modelo202InstalmentUnresolvedReason.VERDICT_UNDECIDED),
    ],
)
def test_the_settlement_folds_an_unfiled_naviera_instalment_below_the_threshold(
    calculation: Modelo202CalculationReading | None,
    kind: Modelo202InstalmentResolutionKind,
    unresolved_reason: Modelo202InstalmentUnresolvedReason | None,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Only a sealed zero calculation counts as nothing paid; an owed or undecided instalment stays open."""
    resolution = resolve_modelo_202_instalment(
        _facts("2P", calculation), filing=None, modality=_REGIME, operation=authority_operation
    )

    assert resolution.kind is kind
    assert resolution.unresolved_reason is unresolved_reason
    if kind is Modelo202InstalmentResolutionKind.NOT_OWED:
        assert resolution.amount == Decimal("0.00")
        assert resolution.grounds is not None
        assert resolution.grounds.outcome is Modelo202InstalmentOutcome.REGIME_CALCULATION_ZERO


def test_the_settlement_owes_every_unfiled_instalment_above_the_threshold(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Above the threshold the naviera is ART_40_3_MANDATORY: even a zero calculation does not excuse filing."""
    profile = _naviera(_threshold(authority_operation) + Decimal("0.01"))
    modality = derive_modelo_202_modality(
        profile, effective_date=date(_year(), 12, 31), authority=authority_operation
    ).modality
    assert modality is Modelo202Modality.ART_40_3_MANDATORY

    resolution = resolve_modelo_202_instalment(
        _facts("2P", _ZERO), filing=None, modality=modality, operation=authority_operation
    )

    assert resolution.kind is Modelo202InstalmentResolutionKind.UNRESOLVED
    assert resolution.unresolved_reason is Modelo202InstalmentUnresolvedReason.OWED_UNFILED
