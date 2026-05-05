"""Tests for the registry-backed deadline engine."""

from __future__ import annotations

from datetime import date

import pytest

from . import (
    AutonomoProfile,
    DeadlineEngine,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
    ScheduleComputationError,
    applies_to,
    explain,
    next_deadline,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _profile(**overrides: object) -> AutonomoProfile:
    base: dict[str, object] = {
        "tax_id": "X1234567L",
        "iva_regime": IVARegime.GENERAL,
        "professional_income_withholding_ge_70pct": False,
    }
    base.update(overrides)
    return AutonomoProfile.model_validate(base)


def _engine() -> DeadlineEngine:
    return DeadlineEngine()


class TestCompute:
    def test_registry_deadline_windows_drive_schedule(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))

        assert [obligation.modelo for obligation in schedule.obligations] == ["130", "130", "130", "130"]
        assert [obligation.period for obligation in schedule.obligations] == [
            "2026Q1",
            "2026Q2",
            "2026Q3",
            "2026Q4",
        ]

    def test_profile_condition_can_remove_registry_deadline(self) -> None:
        schedule = _engine().compute(
            _profile(professional_income_withholding_ge_70pct=True),
            2026,
            today=date(2026, 1, 1),
        )

        assert schedule.obligations == ()

    def test_registry_any_condition_can_add_withholding_deadline_for_employee_payer(self) -> None:
        schedule = _engine().compute(_profile(has_employees=True), 2026, today=date(2026, 1, 1))

        assert [obligation.modelo for obligation in schedule.obligations] == [
            "111",
            "130",
            "111",
            "130",
            "111",
            "130",
            "111",
            "130",
        ]

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
            _profile(uses_objective_estimation_irpf=True),
            2026,
            today=date(2026, 1, 1),
        )

        assert [obligation.modelo for obligation in schedule.obligations if obligation.modelo == "131"] == [
            "131",
            "131",
            "131",
            "131",
        ]

    def test_q1_2026_window_comes_from_registry_data(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        q1 = next(o for o in schedule.obligations if o.period == "2026Q1")

        assert q1.opens_on == date(2026, 4, 1)
        assert q1.closes_on == date(2026, 4, 20)
        assert q1.payment_cutoff_on == date(2026, 4, 15)
        assert q1.boe_references == ("rd-439-2007:art-110",)

    def test_obligations_sorted_by_close_date(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        closes = [o.closes_on for o in schedule.obligations]
        assert closes == sorted(closes)


class TestStatusTransitions:
    def _find_q1(self, schedule: Schedule) -> FilingObligation:
        return next(o for o in schedule.obligations if o.period == "2026Q1")

    def test_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 21))
        assert self._find_q1(schedule).status == ObligationStatus.OVERDUE

    def test_due_today(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 20))
        assert self._find_q1(schedule).status == ObligationStatus.DUE_TODAY

    def test_due_soon(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 7))
        assert self._find_q1(schedule).status == ObligationStatus.DUE_SOON

    def test_upcoming(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        assert self._find_q1(schedule).status == ObligationStatus.UPCOMING


class TestNextDeadline:
    def test_returns_earliest_non_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        result = next_deadline(schedule, today=date(2026, 1, 1))
        assert result is not None
        assert result.period == "2026Q1"

    def test_returns_none_when_all_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        result = next_deadline(schedule, today=date(2999, 1, 1))
        assert result is None


class TestRegistryApplicability:
    def test_applies_to_uses_registry_conditions(self) -> None:
        assert applies_to(_profile(), "130") is True
        assert applies_to(_profile(professional_income_withholding_ge_70pct=True), "130") is False
        assert applies_to(_profile(), "111") is False
        assert applies_to(_profile(has_employees=True), "111") is True
        assert applies_to(_profile(pays_professionals_with_retencion=True), "111") is True
        assert applies_to(_profile(), "115") is False
        assert applies_to(_profile(pays_rent_with_retencion=True), "115") is True
        assert applies_to(_profile(), "123") is False
        assert applies_to(_profile(pays_capital_income_with_retencion=True), "123") is True
        assert applies_to(_profile(), "131") is False
        assert applies_to(_profile(uses_objective_estimation_irpf=True), "131") is True

    def test_explain_uses_registry_condition_text(self) -> None:
        text = explain(_profile(), "130")
        assert "estimacion directa" in text

    def test_unknown_modelo_raises(self) -> None:
        with pytest.raises(ScheduleComputationError):
            explain(_profile(), "999")


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
        with pytest.raises(ScheduleComputationError):
            _engine().compute(_profile(), 1999, today=date(1999, 1, 1))

    def test_negative_due_soon_days_rejected(self) -> None:
        with pytest.raises(ValueError):
            DeadlineEngine(due_soon_days=-1)


class TestScheduleRoundTrip:
    def test_full_round_trip(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        restored = Schedule.model_validate_json(schedule.model_dump_json())
        assert restored == schedule
