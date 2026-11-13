"""Per-instalment Modelo 202 filing verdicts below the LIS art. 40.3 threshold.

Orden HFP/227/2017 art. 1.3 makes the Modelo 202 owed below the threshold only
in an instalment where an ingreso results. These tests drive the real calendar
with the facts one read would gather and check that each instalment gets its own
verdict, that an undecided instalment stays incomplete with the doors that move
it on, and that a base that was never held is not read as zero.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.calculations.registry.applicability_modelo202 import (
    Modelo202BaseBasis,
    Modelo202InstalmentOutcome,
    Modelo202Modality,
    modelo_202_incn_threshold_decimal,
    resolve_modelo_202_art_40_3_incn_threshold,
)
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.contribuyente.entity_type import EntityType
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import IVARegime, ModeloEnrollment, TaxpayerProfile
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ...operator_actions.models import DeclaredNextAction
from ..applicability_evidence import FilingYearApplicabilityEvidence
from ..calendar import build_overview_calendar
from ..calendar_models import OverviewCalendar, OverviewCalendarRange
from ..modelo202_instalment import (
    Modelo202BaseReading,
    Modelo202BaseSource,
    Modelo202CalculationReading,
    Modelo202InstalmentFacts,
    decide_modelo_202_instalment,
    modelo_202_instalment_doors,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_202 = "202"
_MODELO_200 = "200"
_INSTALMENTS = ("1P", "2P", "3P")
_APRIL = _INSTALMENTS[0]
_WORK_UNIT_ID = "a" * 64
_ELECTION_SELECTOR = "taxpayer.pago_fraccionado_art_40_3_elected"
_BUCKET_ID = "modelo-202-instalment-calendar"


def _year() -> int:
    return filing_year_envelope().horizon


def _instalment(token: str) -> Period:
    return Period.from_year_and_code(_year(), token)


def _source() -> Modelo202BaseSource:
    return Modelo202BaseSource(modelo=_MODELO_200, period=Period.from_year_and_code(_year() - 1, "0A"))


def _facts(
    token: str,
    *,
    election: bool | None = False,
    base: Modelo202BaseReading | None = None,
    no_prior_return: bool = False,
    base_source: Modelo202BaseSource | None = None,
    work_unit_id: str | None = None,
    calculation: Modelo202CalculationReading | None = None,
) -> Modelo202InstalmentFacts:
    return Modelo202InstalmentFacts(
        instalment=_instalment(token),
        election_stated=election,
        base_source=base_source or _source(),
        no_prior_return=no_prior_return,
        base=base,
        work_unit_id=work_unit_id,
        calculation=calculation,
    )


def _arguments(door: DeclaredNextAction) -> dict[str, object]:
    return {binding.argument_name: binding.value for binding in door.argument_bindings}


def _legal_entity(operation: PinnedAuthorityOperation) -> TaxpayerProfile:
    threshold = modelo_202_incn_threshold_decimal(
        resolve_modelo_202_art_40_3_incn_threshold(effective_date=date(_year(), 12, 31), authority=operation),
    )
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
        incn_prior_12_months=threshold,
        regimen_entidades_navieras_tonelaje=False,
    )


def _instalment_work_unit(token: str) -> WorkUnit:
    """The instalment's own declaration, opened before anything was calculated or filed."""
    period = _instalment(token)
    revision_id = "modelo-202-instalment-calendar"
    created_at = datetime(_year(), 1, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=_MODELO_202,
            filing_year=_year(),
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(_MODELO_202),
        filing_year=_year(),
        period=period,
        revision_id=revision_id,
        name=f"{_MODELO_202}-{_year()}-{token}",
        created_at=created_at,
        updated_at=created_at,
    )


def _calendar(
    profile: TaxpayerProfile,
    facts_by_token: Mapping[str, Modelo202InstalmentFacts],
    operation: PinnedAuthorityOperation,
    *,
    work_units: tuple[WorkUnit, ...] = (),
) -> OverviewCalendar:
    evidence = FilingYearApplicabilityEvidence(
        profile_for_year=lambda _year: profile,
        ledger_payer_facts_for_year=lambda _year: {},
        modelo_202_instalment_facts=lambda instalment: facts_by_token[instalment.registry_token],
    )
    year = _year()
    return build_overview_calendar(
        profile,
        OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year, 12, 31)),
        operation=operation,
        today=date(year, 1, 1),
        show_suppressed=True,
        work_units=work_units,
        applicability_evidence=evidence,
    )


def test_an_unstated_election_stays_incomplete_whatever_the_base() -> None:
    """The election decides how the base is computed, so without it no base decides anything."""
    positive = Modelo202BaseReading(value=Decimal("100.00"), basis=Modelo202BaseBasis.AEAT_EVIDENCE)
    outcome = decide_modelo_202_instalment(
        _facts("2P", election=None, base=positive), modality=Modelo202Modality.ART_40_2_OPTIONAL
    )
    assert outcome is Modelo202InstalmentOutcome.ELECTION_UNSTATED
    assert outcome.verdict is ApplicabilityVerdict.INCOMPLETE


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("0.01"), Modelo202InstalmentOutcome.BASE_POSITIVE),
        (Decimal("0"), Modelo202InstalmentOutcome.BASE_NOT_POSITIVE),
        (Decimal("-50.00"), Modelo202InstalmentOutcome.BASE_NOT_POSITIVE),
    ],
)
def test_the_art_40_2_base_decides_an_instalment_without_the_election(
    value: Decimal, expected: Modelo202InstalmentOutcome
) -> None:
    base = Modelo202BaseReading(value=value, basis=Modelo202BaseBasis.LOCAL_FILING)
    assert (
        decide_modelo_202_instalment(_facts("2P", base=base), modality=Modelo202Modality.ART_40_2_OPTIONAL) is expected
    )


def test_a_base_never_held_is_not_read_as_zero() -> None:
    outcome = decide_modelo_202_instalment(_facts("2P", base=None), modality=Modelo202Modality.ART_40_2_OPTIONAL)
    assert outcome is Modelo202InstalmentOutcome.BASE_ABSENT
    assert outcome.verdict is ApplicabilityVerdict.INCOMPLETE


def test_no_prior_return_decides_before_the_base_is_looked_for() -> None:
    outcome = decide_modelo_202_instalment(
        _facts("1P", base=None, no_prior_return=True), modality=Modelo202Modality.ART_40_2_OPTIONAL
    )
    assert outcome is Modelo202InstalmentOutcome.NO_PRIOR_RETURN
    assert outcome.verdict is ApplicabilityVerdict.NOT_APPLICABLE


@pytest.mark.parametrize(
    ("calculation", "expected"),
    [
        (None, Modelo202InstalmentOutcome.ELECTED_PENDING_CALCULATION),
        (
            Modelo202CalculationReading(result=Decimal("10.00"), current=False, verified=True),
            Modelo202InstalmentOutcome.ELECTED_PENDING_CALCULATION,
        ),
        (
            Modelo202CalculationReading(result=Decimal("0"), current=False, verified=True),
            Modelo202InstalmentOutcome.ELECTED_PENDING_CALCULATION,
        ),
        (
            Modelo202CalculationReading(result=Decimal("10.00"), current=True, verified=False),
            Modelo202InstalmentOutcome.ELECTED_PENDING_VERIFICATION,
        ),
        (
            Modelo202CalculationReading(result=Decimal("0"), current=True, verified=False),
            Modelo202InstalmentOutcome.ELECTED_PENDING_VERIFICATION,
        ),
        (
            Modelo202CalculationReading(result=Decimal("10.00"), current=True, verified=True),
            Modelo202InstalmentOutcome.ELECTED_CALCULATION_POSITIVE,
        ),
        (
            Modelo202CalculationReading(result=Decimal("0"), current=True, verified=True),
            Modelo202InstalmentOutcome.ELECTED_CALCULATION_ZERO,
        ),
    ],
)
def test_under_the_election_only_a_current_verified_calculation_decides(
    calculation: Modelo202CalculationReading | None, expected: Modelo202InstalmentOutcome
) -> None:
    """Neither a positive nor a zero result decides until a passing verification sealed a current calculation."""
    facts = _facts("2P", election=True, work_unit_id=_WORK_UNIT_ID, calculation=calculation)
    assert decide_modelo_202_instalment(facts, modality=Modelo202Modality.ART_40_2_OPTIONAL) is expected


def test_an_unverified_calculation_opens_its_verification() -> None:
    calculation = Modelo202CalculationReading(result=Decimal("10.00"), current=True, verified=False)
    facts = _facts("2P", election=True, work_unit_id=_WORK_UNIT_ID, calculation=calculation)
    doors = modelo_202_instalment_doors(
        Modelo202InstalmentOutcome.ELECTED_PENDING_VERIFICATION, facts, modelo=_MODELO_202
    )
    assert [door.action.action_id for door in doors] == ["operator.modelo.work.verify"]
    assert _arguments(doors[0]) == {"work_unit_id": _WORK_UNIT_ID}


def test_an_absent_base_opens_the_earlier_modelo_200_first() -> None:
    facts = _facts("2P", base=None, work_unit_id=_WORK_UNIT_ID)
    doors = modelo_202_instalment_doors(Modelo202InstalmentOutcome.BASE_ABSENT, facts, modelo=_MODELO_202)
    assert [door.action.action_id for door in doors] == [
        "operator.modelo.work.create",
        "operator.live.filed.pull",
        "operator.modelo.work.verify",
    ]
    source = _source().period
    assert _arguments(doors[0]) == {
        "modelo": _MODELO_200,
        "year": source.filing_year,
        "period": source.registry_token,
    }
    assert _arguments(doors[2])["work_unit_id"] == _WORK_UNIT_ID


def test_an_absent_base_without_a_work_unit_offers_creating_the_instalment() -> None:
    facts = _facts("2P", base=None)
    doors = modelo_202_instalment_doors(Modelo202InstalmentOutcome.BASE_ABSENT, facts, modelo=_MODELO_202)
    assert doors[2].action.action_id == "operator.modelo.work.create"
    assert _arguments(doors[2])["modelo"] == _MODELO_202


@pytest.mark.parametrize(
    "outcome",
    [
        Modelo202InstalmentOutcome.BASE_POSITIVE,
        Modelo202InstalmentOutcome.BASE_NOT_POSITIVE,
        Modelo202InstalmentOutcome.ELECTED_CALCULATION_POSITIVE,
        Modelo202InstalmentOutcome.ELECTED_CALCULATION_ZERO,
    ],
)
def test_an_outcome_resting_on_recorded_facts_opens_no_door(outcome: Modelo202InstalmentOutcome) -> None:
    assert modelo_202_instalment_doors(outcome, _facts("2P"), modelo=_MODELO_202) == ()


def test_the_calendar_gives_each_instalment_its_own_verdict(authority_operation: PinnedAuthorityOperation) -> None:
    """One year can owe one instalment, be excused another and leave a third undecided."""
    facts = {
        "1P": _facts("1P", no_prior_return=True),
        "2P": _facts("2P", base=Modelo202BaseReading(value=Decimal("120.00"), basis=Modelo202BaseBasis.AEAT_EVIDENCE)),
        "3P": _facts("3P", base=None),
    }
    calendar = _calendar(_legal_entity(authority_operation), facts, authority_operation)
    surfaced = {entry.period.registry_token for entry in calendar.entries if entry.modelo == _MODELO_202}
    suppressed = {
        entry.period.registry_token: entry for entry in calendar.suppressed_entries if entry.modelo == _MODELO_202
    }
    assert surfaced == {"2P"}
    assert set(suppressed) == {"1P", "3P"}
    assert suppressed["1P"].verdict is ApplicabilityVerdict.NOT_APPLICABLE
    assert suppressed["1P"].actions[0].action.action_id == "operator.profile.edit"
    assert suppressed["3P"].verdict is ApplicabilityVerdict.INCOMPLETE
    assert suppressed["3P"].actions[0].action.action_id == "operator.modelo.work.create"


def test_the_calendar_names_the_record_a_base_came_from(authority_operation: PinnedAuthorityOperation) -> None:
    """A base that excuses an instalment states whether it came from a local filing, AEAT or the operator."""
    profile = _legal_entity(authority_operation)
    reasons: dict[Modelo202BaseBasis, str] = {}
    for basis in Modelo202BaseBasis:
        base = Modelo202BaseReading(value=Decimal("0"), basis=basis)
        calendar = _calendar(profile, {token: _facts(token, base=base) for token in _INSTALMENTS}, authority_operation)
        entries = [entry for entry in calendar.suppressed_entries if entry.modelo == _MODELO_202]
        assert {entry.period.registry_token for entry in entries} == set(_INSTALMENTS), basis
        assert all(entry.verdict is ApplicabilityVerdict.NOT_APPLICABLE for entry in entries), basis
        assert len({entry.reason for entry in entries}) == 1, basis
        reasons[basis] = entries[0].reason
    assert len(set(reasons.values())) == len(Modelo202BaseBasis)


def test_the_calendar_keeps_an_unstated_election_incomplete(authority_operation: PinnedAuthorityOperation) -> None:
    facts = {token: _facts(token, election=None) for token in _INSTALMENTS}
    calendar = _calendar(_legal_entity(authority_operation), facts, authority_operation)
    entries = [entry for entry in calendar.suppressed_entries if entry.modelo == _MODELO_202]
    assert {entry.period.registry_token for entry in entries} == set(_INSTALMENTS)
    assert all(entry.verdict is ApplicabilityVerdict.INCOMPLETE for entry in entries)
    assert all(entry.actions[0].action.action_id == "operator.profile.edit" for entry in entries)
    election = [warning for warning in calendar.warnings if warning.code == _ELECTION_SELECTOR]
    assert len(election) == 1
    assert election[0].affected_modelos == (_MODELO_202,)
    assert election[0].fix_action.action.action_id == "operator.profile.edit"


def test_a_stated_election_raises_no_election_warning(authority_operation: PinnedAuthorityOperation) -> None:
    facts = {token: _facts(token, election=False) for token in _INSTALMENTS}
    calendar = _calendar(_legal_entity(authority_operation), facts, authority_operation)
    assert [warning for warning in calendar.warnings if warning.code == _ELECTION_SELECTOR] == []


def test_the_calendar_leaves_the_threshold_verdict_alone(authority_operation: PinnedAuthorityOperation) -> None:
    """Above the threshold filing is mandatory in every instalment; no instalment fact is consulted."""
    profile = _legal_entity(authority_operation)
    above = profile.model_copy(update={"incn_prior_12_months": (profile.incn_prior_12_months or 0) + Decimal("0.01")})

    def refuse(_instalment: Period) -> Modelo202InstalmentFacts:
        raise AssertionError("the threshold verdict needs no instalment facts")

    evidence = FilingYearApplicabilityEvidence(
        profile_for_year=lambda _year: above,
        ledger_payer_facts_for_year=lambda _year: {},
        modelo_202_instalment_facts=refuse,
    )
    year = _year()
    calendar = build_overview_calendar(
        above,
        OverviewCalendarRange(from_date=date(year, 1, 1), to_date=date(year, 12, 31)),
        operation=authority_operation,
        today=date(year, 1, 1),
        show_suppressed=True,
        applicability_evidence=evidence,
    )
    surfaced = {entry.period.registry_token for entry in calendar.entries if entry.modelo == _MODELO_202}
    assert surfaced == set(_INSTALMENTS)


def _attested(value: str) -> Modelo202BaseReading:
    return Modelo202BaseReading(value=Decimal(value), basis=Modelo202BaseBasis.OPERATOR_ATTESTED)


def test_an_opened_declaration_does_not_revive_an_instalment_its_base_excuses(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A 1P declaration holding a stated base of 0.00 is excused by LIS art. 40.2, not shown as due.

    The operator states the base on the instalment's own declaration, so that
    declaration always exists when the statement decides the instalment; its
    existence is not evidence that an ingreso results.
    """
    profile = _legal_entity(authority_operation)
    facts = {token: _facts(token, base=_attested("0.00") if token == _APRIL else None) for token in _INSTALMENTS}
    unit = _instalment_work_unit(_APRIL)
    with_unit = _calendar(profile, facts, authority_operation, work_units=(unit,))
    without_unit = _calendar(profile, facts, authority_operation)
    assert [entry for entry in with_unit.entries if entry.modelo == _MODELO_202] == []
    suppressed = {
        entry.period.registry_token: entry for entry in with_unit.suppressed_entries if entry.modelo == _MODELO_202
    }
    assert suppressed[_APRIL].verdict is ApplicabilityVerdict.NOT_APPLICABLE
    alone = next(
        entry
        for entry in without_unit.suppressed_entries
        if entry.modelo == _MODELO_202 and entry.period.registry_token == _APRIL
    )
    assert suppressed[_APRIL].reason == alone.reason
    assert suppressed[_APRIL].actions == ()


def test_an_opened_declaration_annotates_an_instalment_its_stated_base_makes_owed(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    facts = {token: _facts(token, base=_attested("840.00") if token == _APRIL else None) for token in _INSTALMENTS}
    unit = _instalment_work_unit(_APRIL)
    calendar = _calendar(_legal_entity(authority_operation), facts, authority_operation, work_units=(unit,))
    rows = [entry for entry in calendar.entries if entry.modelo == _MODELO_202]
    assert [entry.period.registry_token for entry in rows] == [_APRIL]
    assert rows[0].local_work_unit_id == unit.work_unit_id
    assert _APRIL not in {
        entry.period.registry_token for entry in calendar.suppressed_entries if entry.modelo == _MODELO_202
    }


def test_an_opened_declaration_without_a_stated_base_stays_undecided(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Opening the declaration states nothing, so the instalment keeps its doors rather than a due row."""
    unit = _instalment_work_unit(_APRIL)
    facts = {
        token: _facts(token, base=None, work_unit_id=unit.work_unit_id if token == _APRIL else None)
        for token in _INSTALMENTS
    }
    calendar = _calendar(_legal_entity(authority_operation), facts, authority_operation, work_units=(unit,))
    assert [entry for entry in calendar.entries if entry.modelo == _MODELO_202] == []
    first = next(
        entry
        for entry in calendar.suppressed_entries
        if entry.modelo == _MODELO_202 and entry.period.registry_token == _APRIL
    )
    assert first.verdict is ApplicabilityVerdict.INCOMPLETE
    assert first.actions[-1].action.action_id == "operator.modelo.work.verify"
    assert _arguments(first.actions[-1]) == {"work_unit_id": unit.work_unit_id}
