"""Tests for the registry-backed deadline engine."""

from __future__ import annotations

from collections import Counter
from datetime import date

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ...calculations.registry.deadline_coordinate import DeadlineSemanticCoordinate, deadline_semantic_coordinate
from ...calculations.registry.schedules import applicable_filing_schedules, evaluate_profile_conditions
from ...calculations.registry.tests.authored_editions import deadline_source_with_sha256, source_exercise
from ...calculations.registry.tests.legal_text import legal_text_match, spanish_date
from ...calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_supported_filing_years,
)
from ..engine import DeadlineEngine, applies_to, explain, next_deadline
from ..errors import DeadlineValidationError, NoDeadlineWindowsError, ScheduleComputationError
from ..models import (
    IrpfEstimationRegime,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloDeadline,
    ModeloEnrollment,
    ModeloIVAProfile,
    ObligationStatus,
    Schedule,
    TaxpayerProfile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_SUPPORTED_YEARS = PublishedGovernedFactSource().supported_filing_years().years
# The AEAT Calendario del contribuyente whose pinned PDF prints the Modelo 130 first
# quarter as April 1-20 with direct debit through April 15; the exercise is the one
# the Modelo 130 windows cite it for.
_M130_Q1_CALENDAR_EXERCISE = source_exercise(
    deadline_source_with_sha256("130", "8bc91454ece63a0139f1c0948637239a8c7b2b20fe17dd534b266cb46c0e631b")
)
# The AEAT Calendario del contribuyente whose pinned PDF (with the next edition's
# January entries for its fourth quarter) grounds the Modelo 130 carry chain below.
_M130_CARRY_CHAIN_CALENDAR_EXERCISE = source_exercise(
    deadline_source_with_sha256("130", "dfdcae8889ab5fecffa368e235d933676c8a479915e09b107734f8339eed0f50")
)


def _renta_campaign(legal_ref: str, cutoff_month: int, cutoff_day: int) -> tuple[int, str, date, date, date]:
    """Read one IRPF campaign's plazo general from its Orden and the ejercicio it declares.

    The Orden prints the window as "entre los dias <d> de <mes> y <d> de <mes> de <año>";
    the campaign declares the ejercicio before the year it runs in. The domiciliación
    cutoff (the Orden's art. 13.3, not in the bundled corpus) is given as a day of that year.
    """
    match = legal_text_match(legal_ref, r"entre los dias (\d{1,2}) de (\w+) y (\d{1,2}) de (\w+) de (\d{4})")
    opens_day, opens_month, closes_day, closes_month, year = match.groups()
    closes_on = spanish_date(closes_day, closes_month, year)
    return (
        closes_on.year - 1,
        legal_ref,
        spanish_date(opens_day, opens_month, year),
        closes_on,
        date(closes_on.year, cutoff_month, cutoff_day),
    )


# Each IRPF campaign's plazo general, read from its Orden's own article: Orden
# HAC/277/2026 art. 7 and Orden HAC/265/2024 art. 8.
_RENTA_CAMPAIGNS = (
    pytest.param(*_renta_campaign("orden-hac-277-2026:art-7", 6, 25), id="orden-hac-277-art-7"),
    pytest.param(*_renta_campaign("orden-hac-265-2024:art-8", 6, 26), id="orden-hac-265-art-8"),
)


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


def _profile(**overrides: object) -> TaxpayerProfile:
    base: dict[str, object] = {
        "tax_id": "X1234567L",
        "iva_regime": IVARegime("GENERAL"),
        "iva": ModeloIVAProfile(
            tax_territory=M303TaxTerritory.from_registry("common_regime"),
            regime_composition=M303RegimeComposition.from_registry("general"),
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
        "professional_income_withholding_ge_70pct": False,
        "art109_activity_income_withholding_ge_70pct": False,
    }
    base.update(overrides)
    return TaxpayerProfile.model_validate(base)


def _engine() -> DeadlineEngine:
    return DeadlineEngine()


def _assert_exact_once(
    actual: list[DeadlineSemanticCoordinate],
    expected: list[DeadlineSemanticCoordinate],
) -> None:
    actual_counts = Counter(actual)
    assert actual_counts == Counter(expected)
    assert all(multiplicity == 1 for multiplicity in actual_counts.values())


class TestCompute:
    def test_registry_deadline_windows_drive_schedule(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))

        # Verify that M130 and M303 quarterly windows are present and sorted by
        # close date. The full obligation set is larger — modelos with
        # unconditional filing schedules (M347, M390, etc.) also appear; those
        # missing profile conditions are a registry data quality gap tracked
        # separately. The intent here is to assert that registry-sourced window
        # data drives dates and periods correctly for the core autónomo obligations.
        irpf_iva = [
            (obligation.modelo, obligation.period)
            for obligation in schedule.obligations
            if obligation.modelo in {"130", "303"}
        ]
        assert irpf_iva == [
            ("130", _period(2026, "1T")),
            ("303", _period(2026, "1T")),
            ("130", _period(2026, "2T")),
            ("303", _period(2026, "2T")),
            ("130", _period(2026, "3T")),
            ("303", _period(2026, "3T")),
            ("130", _period(2026, "4T")),
            ("303", _period(2026, "4T")),
        ]

    def test_profile_condition_can_remove_registry_deadline(self) -> None:
        schedule = _engine().compute(
            _profile(art109_activity_income_withholding_ge_70pct=True),
            2026,
            today=date(2026, 1, 1),
        )

        modelos = [obligation.modelo for obligation in schedule.obligations]
        assert "130" not in modelos, "M130 must be absent when the Art. 109 activity-income fact is true"
        assert modelos.count(Modelo("303")) == 4, "M303 must appear for all four quarters"

    def test_professional_only_high_retention_field_does_not_remove_m130_deadline(self) -> None:
        schedule = _engine().compute(
            _profile(professional_income_withholding_ge_70pct=True),
            2026,
            today=date(2026, 1, 1),
        )

        assert [obligation.modelo for obligation in schedule.obligations].count(Modelo("130")) == 4

    def test_registry_any_condition_can_add_withholding_deadline_for_employee_payer(self) -> None:
        schedule = _engine().compute(_profile(has_employees=True), 2026, today=date(2026, 1, 1))

        modelos = [obligation.modelo for obligation in schedule.obligations]
        assert modelos.count(Modelo("111")) == 4, "M111 must appear for all four quarters when has_employees=True"
        assert modelos.count(Modelo("130")) == 4
        assert modelos.count(Modelo("303")) == 4

    def test_registry_any_condition_can_add_withholding_deadline_for_professional_payer(self) -> None:
        schedule = _engine().compute(
            _profile(pays_professionals_with_retencion=True),
            2026,
            today=date(2026, 1, 1),
        )

        assert [obligation.modelo for obligation in schedule.obligations if obligation.modelo == "111"] == [
            "111",
            "111",
            "111",
            "111",
        ]

    def test_profile_based_schedule_selects_monthly_withholding_deadlines_for_large_company(self) -> None:
        schedule = _engine().compute(
            _profile(
                has_employees=True,
                enrollment=ModeloEnrollment(large_company=True),
            ),
            2026,
            today=date(2026, 1, 1),
        )
        withholding_periods = [obligation.period for obligation in schedule.obligations if obligation.modelo == "111"]

        assert withholding_periods == [
            _period(2026, "01"),
            _period(2026, "02"),
            _period(2026, "03"),
            _period(2026, "04"),
            _period(2026, "05"),
            _period(2026, "06"),
            _period(2026, "07"),
            _period(2026, "08"),
            _period(2026, "09"),
            _period(2026, "10"),
            _period(2026, "11"),
            _period(2026, "12"),
        ]

    def test_intracommunity_profile_selects_quarterly_modelo_349_when_threshold_is_not_exceeded(self) -> None:
        schedule = _engine().compute(
            _profile(does_intracomunitario=True),
            2026,
            today=date(2026, 1, 1),
        )
        periods = [obligation.period for obligation in schedule.obligations if obligation.modelo == "349"]

        assert periods == [_period(2026, quarter) for quarter in ("1T", "2T", "3T", "4T")]

    def test_intracommunity_threshold_selects_monthly_modelo_349(self) -> None:
        schedule = _engine().compute(
            _profile(
                does_intracomunitario=True,
                iva=ModeloIVAProfile(
                    tax_territory=M303TaxTerritory.from_registry("common_regime"),
                    regime_composition=M303RegimeComposition.from_registry("general"),
                    intracommunity_operations_exceed_50000_eur=True,
                    redeme_enrolled=False,
                    cash_accounting_regime_enrolled=False,
                    voluntary_sii_enrolled=False,
                    hydrocarbon_deposit_advance_payment_deduction_entitled=False,
                ),
            ),
            2026,
            today=date(2026, 1, 1),
        )
        periods = [obligation.period for obligation in schedule.obligations if obligation.modelo == "349"]

        assert periods == [
            _period(2026, "01"),
            _period(2026, "02"),
            _period(2026, "03"),
            _period(2026, "04"),
            _period(2026, "05"),
            _period(2026, "06"),
            _period(2026, "07"),
            _period(2026, "08"),
            _period(2026, "09"),
            _period(2026, "10"),
            _period(2026, "11"),
            _period(2026, "12"),
        ]

    @pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
    def test_modelo_303_emits_exact_quarterly_or_monthly_cadence_from_profile(self, filing_year: int) -> None:
        quarterly = _engine().compute(_profile(), filing_year, today=date(filing_year, 1, 1))
        monthly = _engine().compute(
            _profile(
                iva=ModeloIVAProfile(
                    tax_territory=M303TaxTerritory.from_registry("common_regime"),
                    regime_composition=M303RegimeComposition.from_registry("general"),
                    redeme_enrolled=True,
                    cash_accounting_regime_enrolled=False,
                    voluntary_sii_enrolled=False,
                    hydrocarbon_deposit_advance_payment_deduction_entitled=False,
                ),
            ),
            filing_year,
            today=date(filing_year, 1, 1),
        )

        assert [item.period.registry_token for item in quarterly.obligations if item.modelo == "303"] == [
            "1T",
            "2T",
            "3T",
            "4T",
        ]
        assert [item.period.registry_token for item in monthly.obligations if item.modelo == "303"] == [
            f"{month:02d}" for month in range(1, 13)
        ]

    def test_precalculation_schedule_does_not_emit_qualified_m210_variants(self) -> None:
        schedule = _engine().compute(_profile(), 2025, today=date(2025, 1, 1))

        assert all(item.modelo != "210" for item in schedule.obligations)

    def test_periodic_coordinate_gate_rejects_dropped_and_duplicate_rows(self) -> None:
        expected = [
            deadline_semantic_coordinate("303", _period(2025, "1T"), None, None),
            deadline_semantic_coordinate("303", _period(2025, "2T"), None, None),
        ]

        with pytest.raises(AssertionError):
            _assert_exact_once(expected[1:], expected)
        with pytest.raises(AssertionError):
            _assert_exact_once([*expected, expected[0]], expected)

    @pytest.mark.parametrize("monthly_iva", [False, True])
    def test_compute_preserves_each_applicable_authored_precalculation_coordinate_once(
        self,
        monthly_iva: bool,
    ) -> None:
        profile = _profile(
            iva=ModeloIVAProfile(
                tax_territory=M303TaxTerritory.from_registry("common_regime"),
                regime_composition=M303RegimeComposition.from_registry("general"),
                redeme_enrolled=monthly_iva,
                cash_accounting_regime_enrolled=False,
                voluntary_sii_enrolled=False,
                hydrocarbon_deposit_advance_payment_deduction_entitled=False,
            ),
        )
        supported_years = published_supported_filing_years()
        assert supported_years is not None

        for filing_year in supported_years.years:
            expected = []
            for modelo, revision, window in _engine().deadline_windows(filing_year):
                # Qualified windows (currently M210 resultado/tipo-renta variants)
                # resolve only after calculation and are intentionally absent from
                # the pre-calculation schedule. Every unqualified authored window,
                # periodic or annual, belongs in this fleet comparison.
                if window.resultado_scope is not None or window.tipo_renta_scope is not None:
                    continue
                coordinate = deadline_semantic_coordinate(modelo, window.period, None, None)

                schedule_applies = not revision.filing_schedules or bool(
                    applicable_filing_schedules(
                        revision,
                        profile,
                        period=window.period.registry_token,
                    ),
                )
                conditions_apply = (
                    evaluate_profile_conditions(
                        window.applicability_conditions,
                        profile,
                        mode=window.applicability_condition_mode,
                    )
                    is not None
                )
                if schedule_applies and conditions_apply:
                    expected.append(coordinate)

            schedule = _engine().compute(profile, filing_year, today=date(filing_year, 1, 1))
            actual = [
                deadline_semantic_coordinate(item.modelo, item.period, None, None) for item in schedule.obligations
            ]

            _assert_exact_once(actual, expected)

    def test_registry_condition_can_add_rental_withholding_deadline(self) -> None:
        schedule = _engine().compute(_profile(pays_rent_with_retencion=True), 2026, today=date(2026, 1, 1))

        assert [obligation.modelo for obligation in schedule.obligations if obligation.modelo == "115"] == [
            "115",
            "115",
            "115",
            "115",
        ]

    def test_registry_condition_can_add_capital_income_withholding_deadline(self) -> None:
        schedule = _engine().compute(
            _profile(pays_capital_income_with_retencion=True),
            2026,
            today=date(2026, 1, 1),
        )

        assert [obligation.modelo for obligation in schedule.obligations if obligation.modelo == "123"] == [
            "123",
            "123",
            "123",
            "123",
        ]

    def test_registry_condition_can_add_objective_estimation_deadline(self) -> None:
        schedule = _engine().compute(
            _profile(irpf_estimation_regime=IrpfEstimationRegime.from_registry("objetiva")),
            2026,
            today=date(2026, 1, 1),
        )

        assert [obligation.modelo for obligation in schedule.obligations if obligation.modelo == "131"] == [
            "131",
            "131",
            "131",
            "131",
        ]

    def test_modelo_130_first_quarter_window_comes_from_registry_data(self) -> None:
        year = _M130_Q1_CALENDAR_EXERCISE
        schedule = _engine().compute(_profile(), year, today=date(year, 1, 1))
        q1 = next(o for o in schedule.obligations if o.modelo == "130" and o.period == _period(year, "1T"))

        assert q1.opens_on == date(year, 4, 1)
        assert q1.closes_on == date(year, 4, 20)
        assert q1.payment_cutoff_on == date(year, 4, 15)
        assert "rd-439-2007:art-110" in q1.boe_references

    def test_modelo_130_calendar_windows_cover_same_year_carry_chain(self) -> None:
        """M130 deadlines are present so local filing can seed later quarters.

        External authority: AEAT Calendario del contribuyente 2025 lists
        Modelos 130/131 quarterly presentation windows as April 1-21,
        July 1-21, and October 1-20, with direct debit cutoffs April 15,
        July 16, and October 15. The 2026 calendar lists the 2025 fourth
        quarter window as January 1-30, with direct debit through January 27.
        """
        year = _M130_CARRY_CHAIN_CALENDAR_EXERCISE
        schedule = _engine().compute(_profile(), year, today=date(year + 1, 6, 29))
        rows = {
            obligation.period.registry_token: (
                obligation.opens_on,
                obligation.closes_on,
                obligation.payment_cutoff_on,
                obligation.status,
            )
            for obligation in schedule.obligations
            if obligation.modelo == "130"
        }

        assert rows == {
            "1T": (date(year, 4, 1), date(year, 4, 21), date(year, 4, 15), ObligationStatus.OVERDUE),
            "2T": (date(year, 7, 1), date(year, 7, 21), date(year, 7, 16), ObligationStatus.OVERDUE),
            "3T": (date(year, 10, 1), date(year, 10, 20), date(year, 10, 15), ObligationStatus.OVERDUE),
            "4T": (date(year + 1, 1, 1), date(year + 1, 1, 30), date(year + 1, 1, 27), ObligationStatus.OVERDUE),
        }

    def test_obligations_sorted_by_close_date(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        closes = [o.closes_on for o in schedule.obligations]
        assert closes == sorted(closes)


class TestPreRegistrationObligationGate:
    """The deadline engine must not invent pre-registration obligations.

    A registrant running the backlog must not be shown overdue IVA quarters
    of an earlier exercise — obligations from before
    they had any economic activity. With ``activity_start_date`` set,
    the engine suppresses every window that closes before the alta;
    with it unset, behaviour is unchanged.
    """

    @pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
    def test_registrant_after_the_exercise_has_no_iva_obligations_for_it(self, filing_year: int) -> None:
        """A profile registered the following year owes no quarterly return for the exercise.

        Computing the schedule for a taxpayer whose censo alta is March 1
        of the following year must drop every Modelo 303 window — all four
        quarters close before the alta date."""

        alta = date(filing_year + 1, 3, 1)
        profile = _profile(activity_start_date=alta)
        schedule = _engine().compute(profile, filing_year, today=date(filing_year + 1, 5, 21))

        assert all(o.modelo != "303" for o in schedule.obligations), (
            f"a {alta} registrant was shown a {filing_year} IVA quarter that closed before their censo alta"
        )
        assert all(o.closes_on >= alta for o in schedule.obligations), (
            "an obligation window closing before the alta survived the gate"
        )

    @pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
    def test_unset_activity_start_date_keeps_the_full_schedule(self, filing_year: int) -> None:
        """A profile with no alta date keeps the full schedule.

        The gate is opt-in: when ``activity_start_date`` is ``None`` no
        window is suppressed, so the schedule still carries the
        four quarterly Modelo 303 obligations."""

        profile = _profile()
        assert profile.activity_start_date is None
        schedule = _engine().compute(profile, filing_year, today=date(filing_year + 1, 5, 21))

        iva_quarters = sorted((o.period for o in schedule.obligations if o.modelo == "303"), key=lambda p: p.code)
        assert iva_quarters == [_period(filing_year, code) for code in ("1T", "2T", "3T", "4T")]

    @pytest.mark.parametrize("filing_year", _SUPPORTED_YEARS)
    def test_alta_inside_the_exercise_keeps_only_post_alta_quarters(self, filing_year: int) -> None:
        """A mid-year alta keeps only the windows closing on or after it.

        A taxpayer who registered on September 1 owes the Q3 return (window
        closes in October, after the alta) and Q4, but not Q1 / Q2 —
        those windows closed before they had any activity."""

        profile = _profile(activity_start_date=date(filing_year, 9, 1))
        schedule = _engine().compute(profile, filing_year, today=date(filing_year + 1, 5, 21))

        iva_quarters = sorted((o.period for o in schedule.obligations if o.modelo == "303"), key=lambda p: p.code)
        assert iva_quarters == [_period(filing_year, "3T"), _period(filing_year, "4T")]


class TestStatusTransitions:
    def _find_q1(self, schedule: Schedule) -> ModeloDeadline:
        return next(o for o in schedule.obligations if o.period == _period(2026, "1T"))

    def test_q1_status_transitions(self) -> None:
        cases = (
            (date(2026, 4, 21), ObligationStatus.OVERDUE),
            (date(2026, 4, 20), ObligationStatus.DUE_TODAY),
            (date(2026, 4, 7), ObligationStatus.DUE_SOON),
            (date(2026, 1, 1), ObligationStatus.UPCOMING),
        )

        for today, expected_status in cases:
            schedule = _engine().compute(_profile(), 2026, today=today)
            assert self._find_q1(schedule).status == expected_status, today


class TestNextDeadline:
    def test_returns_earliest_non_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        result = next_deadline(schedule, today=date(2026, 1, 1))
        assert result is not None
        # next_deadline returns the obligation with the earliest closing date
        # that is not yet overdue on the reference day.
        earliest_close = min(o.closes_on for o in schedule.obligations)
        assert result.closes_on == earliest_close

    def test_returns_none_when_all_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        result = next_deadline(schedule, today=date(2999, 1, 1))
        assert result is None


class TestRegistryApplicability:
    def test_applies_to_uses_registry_conditions(self) -> None:
        assert applies_to(_profile(), "130") is True
        assert applies_to(_profile(professional_income_withholding_ge_70pct=True), "130") is True
        assert applies_to(_profile(art109_activity_income_withholding_ge_70pct=True), "130") is False
        assert applies_to(_profile(), "111") is False
        assert applies_to(_profile(has_employees=True), "111") is True
        assert applies_to(_profile(pays_professionals_with_retencion=True), "111") is True
        assert applies_to(_profile(), "115") is False
        assert applies_to(_profile(pays_rent_with_retencion=True), "115") is True
        assert applies_to(_profile(), "123") is False
        assert applies_to(_profile(pays_capital_income_with_retencion=True), "123") is True
        assert applies_to(_profile(), "131") is False
        assert (
            applies_to(_profile(irpf_estimation_regime=IrpfEstimationRegime.from_registry("objetiva")), "131") is True
        )

    def test_explain_uses_registry_condition_text(self) -> None:
        text = explain(_profile(), "130")
        assert "estimacion directa" in text

    def test_unknown_modelo_raises(self) -> None:
        # The benign no-windows fault is the narrow NoDeadlineWindowsError
        # subtype so callers can degrade gracefully around it. The refusal
        # carries its registered key and the modelo as a machine fact; the
        # absence assertion on str(exc) is in test_engine_refusal_contract.
        with pytest.raises(NoDeadlineWindowsError) as excinfo:
            explain(_profile(), "999")

        assert excinfo.value.context is not None
        assert excinfo.value.context["modelo"] == "999"


class TestAnnualFilingWindows:
    """The IRPF Renta and IVA/informative annual filing windows must be
    registered so they resolve through the deadline engine.

    Grounding for the IRPF dates:

    * Orden HAC/277/2026, art. 7 — IRPF ejercicio 2025: plazo general
      8 de abril a 30 de junio de 2026; domiciliacion hasta el 25 de
      junio de 2026.
    * Orden HAC/265/2024, art. 8 — IRPF ejercicio 2023: plazo general
      3 de abril a 1 de julio de 2024; domiciliacion hasta el 26 de
      junio de 2024.
    """

    @pytest.mark.parametrize(
        ("filing_year", "legal_ref", "opens_on", "closes_on", "payment_cutoff_on"), _RENTA_CAMPAIGNS
    )
    def test_modelo_100_window_resolves_for_each_grounded_renta_campaign(
        self,
        filing_year: int,
        legal_ref: str,
        opens_on: date,
        closes_on: date,
        payment_cutoff_on: date,
    ) -> None:
        windows = [window for code, _revision, window in _engine().deadline_windows(filing_year) if code == "100"]
        assert len(windows) == 1
        window = windows[0]
        assert window.id == f"modelo-100-{filing_year}-0a"
        assert window.period_kind == "annual"
        assert window.opens_on == opens_on
        assert window.closes_on == closes_on
        assert window.payment_cutoff_on == payment_cutoff_on
        assert legal_ref in window.legal_refs

    @pytest.mark.parametrize(
        ("filing_year", "_legal_ref", "opens_on", "closes_on", "payment_cutoff_on"), _RENTA_CAMPAIGNS
    )
    def test_modelo_100_tax_year_schedule_carries_its_following_campaign_window(
        self,
        filing_year: int,
        _legal_ref: str,
        opens_on: date,
        closes_on: date,
        payment_cutoff_on: date,
    ) -> None:
        schedule = _engine().compute(_profile(), filing_year, today=opens_on)

        obligation = next(
            item for item in schedule.obligations if item.modelo == "100" and item.period == _period(filing_year, "0A")
        )

        assert (obligation.opens_on, obligation.closes_on, obligation.payment_cutoff_on) == (
            opens_on,
            closes_on,
            payment_cutoff_on,
        )

    def test_modelo_100_explain_no_longer_errors(self) -> None:
        engine = _engine()
        assert engine.explain(_profile(), "100", year=2025)
        assert engine.explain(_profile(), "100", year=2023)

    def test_modelo_303_quarterly_windows_resolve(self) -> None:
        for year in (2024, 2025, 2026):
            quarterly_periods = sorted(
                (
                    window.period
                    for code, _revision, window in _engine().deadline_windows(year)
                    if code == "303" and window.period_kind == "quarterly"
                ),
                key=lambda p: p.code,
            )
            assert quarterly_periods == [
                _period(year, "1T"),
                _period(year, "2T"),
                _period(year, "3T"),
                _period(year, "4T"),
            ]
            # SII-enrolled monthly windows also appear; assert they are present as a
            # regression guard.
            monthly_periods = sorted(
                (
                    window.period
                    for code, _revision, window in _engine().deadline_windows(year)
                    if code == "303" and window.period_kind == "monthly"
                ),
                key=lambda p: p.code,
            )
            assert len(monthly_periods) > 0, f"M303 monthly windows absent for {year}"
        january_2026 = next(
            window
            for code, _revision, window in _engine().deadline_windows(2026)
            if code == "303" and window.period == _period(2026, "01")
        )
        assert january_2026.closes_on == date(2026, 3, 2)
        assert january_2026.payment_cutoff_on == date(2026, 2, 25)

    def test_modelo_347_annual_window_resolves(self) -> None:
        for year, closes_on in ((2025, date(2026, 3, 2)), (2026, date(2027, 2, 28))):
            windows = [window for code, _revision, window in _engine().deadline_windows(year) if code == "347"]
            assert [window.period for window in windows] == [_period(year, "0A")]
            assert windows[0].closes_on == closes_on

    @pytest.mark.parametrize(
        ("filing_year", "opens_on", "closes_on"),
        (
            (2024, date(2025, 1, 1), date(2025, 1, 31)),
            (2025, date(2026, 1, 1), date(2026, 1, 31)),
        ),
    )
    def test_modelo_180_january_window_resolves_under_its_tax_year(
        self,
        filing_year: int,
        opens_on: date,
        closes_on: date,
    ) -> None:
        schedule = _engine().compute(_profile(), filing_year, today=opens_on)

        obligation = next(
            item for item in schedule.obligations if item.modelo == "180" and item.period == _period(filing_year, "0A")
        )

        assert obligation.opens_on == opens_on
        assert obligation.closes_on == closes_on


class TestEnginePurity:
    def test_compute_does_not_mutate_profile(self) -> None:
        profile = _profile()
        original = profile.model_dump()
        _engine().compute(profile, 2026, today=date(2026, 1, 1))
        assert profile.model_dump() == original

    def test_compute_is_deterministic_modulo_generated_at(self) -> None:
        engine = _engine()
        profile = _profile()
        a = engine.compute(profile, 2026, today=date(2026, 1, 1))
        b = engine.compute(profile, 2026, today=date(2026, 1, 1))
        assert a.obligations == b.obligations
        assert a.profile == b.profile
        assert a.year == b.year


class TestComputeFailures:
    def test_missing_registry_year_raises(self) -> None:
        # A year with no registered windows raises the narrow
        # NoDeadlineWindowsError — the benign data gap, not a genuine
        # registry-integrity fault. It is still a ScheduleComputationError
        # subclass, so existing broad callers keep working.
        with pytest.raises(NoDeadlineWindowsError) as excinfo:
            _engine().compute(_profile(), 1999, today=date(1999, 1, 1))
        assert isinstance(excinfo.value, ScheduleComputationError)
        assert excinfo.value.context == {"filing_year": 1999}

    def test_negative_due_soon_days_rejected(self) -> None:
        with pytest.raises(DeadlineValidationError, match=r"due_soon_days must be >= 0"):
            DeadlineEngine(due_soon_days=-1)


class TestScheduleRoundTrip:
    def test_full_round_trip(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        restored = Schedule.model_validate_json(schedule.model_dump_json())
        assert restored == schedule
