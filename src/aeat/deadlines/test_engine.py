"""Unit tests for :class:`aeat.deadlines.DeadlineEngine` and ``next_deadline``."""

from __future__ import annotations

from datetime import date

import pytest

from . import (
    KNOWN_AUTONOMO_MODELOS,
    AutonomoProfile,
    DeadlineEngine,
    FilingObligation,
    IVARegime,
    ModeloCatalogueLoader,
    ModeloIdentifier,
    ObligationStatus,
    Schedule,
    ScheduleComputationError,
    next_deadline,
)

pytestmark = pytest.mark.unit


class _Catalogue:
    """Real Protocol-conforming test double - never a mock/patch/stub.

    Implements :class:`aeat.deadlines.ModeloCatalogueLoader` over the
    closed v1 set of autónomo modelos.
    """

    def known_modelos(self) -> tuple[ModeloIdentifier, ...]:
        return tuple(ModeloIdentifier(m) for m in KNOWN_AUTONOMO_MODELOS)

    def is_known(self, modelo: ModeloIdentifier) -> bool:
        return modelo in KNOWN_AUTONOMO_MODELOS


def _profile(**overrides: object) -> AutonomoProfile:
    base: dict[str, object] = {
        "tax_id": "X1234567L",
        "iva_regime": IVARegime.GENERAL,
        "has_employees": False,
        "pays_professionals_with_retencion": False,
        "professional_income_withholding_ge_70pct": False,
        "pays_rent_with_retencion": False,
        "does_intracomunitario": False,
        "third_party_transactions_above_347_threshold": False,
        "bienes_extranjero_above_threshold": False,
    }
    base.update(overrides)
    return AutonomoProfile.model_validate(base)


def _engine() -> DeadlineEngine:
    return DeadlineEngine(_Catalogue())


class TestProtocolConformance:
    """The in-test catalogue is a real Protocol implementation."""

    def test_runtime_checkable(self) -> None:
        assert isinstance(_Catalogue(), ModeloCatalogueLoader)


class TestComputeMembership:
    """``compute`` emits the right modelo set per profile flag combination."""

    def test_baseline_profile_emits_irpf_iva_set(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        modelos = {o.modelo for o in schedule.obligations}
        assert {"100", "130", "303", "390"}.issubset(modelos)
        assert "111" not in modelos
        assert "115" not in modelos
        assert "180" not in modelos
        assert "190" not in modelos
        assert "347" not in modelos
        assert "349" not in modelos
        assert "720" not in modelos

    def test_full_flagged_profile_emits_everything(self) -> None:
        profile = _profile(
            has_employees=True,
            pays_professionals_with_retencion=True,
            pays_rent_with_retencion=True,
            does_intracomunitario=True,
            third_party_transactions_above_347_threshold=True,
            bienes_extranjero_above_threshold=True,
        )
        schedule = _engine().compute(profile, 2026, today=date(2026, 1, 1))
        modelos = {o.modelo for o in schedule.obligations}
        assert set(KNOWN_AUTONOMO_MODELOS) == modelos

    def test_recargo_equivalencia_drops_303_390(self) -> None:
        profile = _profile(iva_regime=IVARegime.RECARGO_EQUIVALENCIA)
        schedule = _engine().compute(profile, 2026, today=date(2026, 1, 1))
        modelos = {o.modelo for o in schedule.obligations}
        assert "303" not in modelos
        assert "390" not in modelos
        assert "130" in modelos
        assert "100" in modelos

    def test_professional_withholding_exception_drops_130(self) -> None:
        profile = _profile(professional_income_withholding_ge_70pct=True)
        schedule = _engine().compute(profile, 2026, today=date(2026, 1, 1))
        modelos = {o.modelo for o in schedule.obligations}
        assert "130" not in modelos
        assert "100" in modelos
        assert "303" in modelos


class TestComputeWindows:
    """Each emitted obligation matches the canonical window for its period."""

    def test_303_q1_2026_window(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        q1 = next(o for o in schedule.obligations if o.modelo == "303" and o.period == "2026Q1")
        assert q1.opens_on == date(2026, 4, 1)
        assert q1.closes_on == date(2026, 4, 20)
        assert q1.payment_cutoff_on == date(2026, 4, 15)
        assert "BOE-Orden-IVA-autoliquidacion" in q1.boe_references

    def test_347_2026_window(self) -> None:
        schedule = _engine().compute(
            _profile(third_party_transactions_above_347_threshold=True),
            2026,
            today=date(2026, 1, 1),
        )
        annual = next(o for o in schedule.obligations if o.modelo == "347" and o.period == "2026")
        assert annual.opens_on == date(2027, 2, 1)
        assert annual.closes_on == date(2027, 3, 1)
        assert "BOE-Orden-347-Operaciones-Terceros" in annual.boe_references

    def test_obligations_sorted_by_close_date(self) -> None:
        schedule = _engine().compute(
            _profile(
                has_employees=True,
                pays_rent_with_retencion=True,
            ),
            2026,
            today=date(2026, 1, 1),
        )
        closes = [o.closes_on for o in schedule.obligations]
        assert closes == sorted(closes)


class TestStatusTransitions:
    """`_classify` transitions across the four engine-produced statuses."""

    def _q1_close(self) -> date:
        return date(2026, 4, 20)

    def _find_303_q1(self, schedule: Schedule) -> FilingObligation:
        return next(o for o in schedule.obligations if o.modelo == "303" and o.period == "2026Q1")

    def test_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 21))
        assert self._find_303_q1(schedule).status == ObligationStatus.OVERDUE

    def test_due_today(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=self._q1_close())
        assert self._find_303_q1(schedule).status == ObligationStatus.DUE_TODAY

    def test_due_soon(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 7))
        assert self._find_303_q1(schedule).status == ObligationStatus.DUE_SOON

    def test_upcoming(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        assert self._find_303_q1(schedule).status == ObligationStatus.UPCOMING

    def test_due_soon_threshold_inclusive(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 6))
        assert self._find_303_q1(schedule).status == ObligationStatus.DUE_SOON

    def test_due_soon_threshold_exclusive(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 5))
        assert self._find_303_q1(schedule).status == ObligationStatus.UPCOMING


class TestNextDeadline:
    """Edge cases for :func:`next_deadline`."""

    def test_returns_earliest_non_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        result = next_deadline(schedule, today=date(2026, 1, 1))
        assert result is not None
        assert result.closes_on >= date(2026, 1, 1)

    def test_returns_none_when_all_overdue(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 1, 1))
        result = next_deadline(schedule, today=date(2999, 1, 1))
        assert result is None

    def test_due_today_is_returned(self) -> None:
        schedule = _engine().compute(_profile(), 2026, today=date(2026, 4, 20))
        result = next_deadline(schedule, today=date(2026, 4, 20))
        assert result is not None
        assert result.closes_on == date(2026, 4, 20)


class TestEnginePurity:
    """The engine performs no I/O and never mutates inputs."""

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
    """Failure modes raise typed errors from the AeatError hierarchy."""

    def test_unsupported_year_raises(self) -> None:
        with pytest.raises(ScheduleComputationError):
            _engine().compute(_profile(), 1999, today=date(1999, 1, 1))

    def test_negative_due_soon_days_rejected(self) -> None:
        with pytest.raises(ValueError):
            DeadlineEngine(_Catalogue(), due_soon_days=-1)


class TestScheduleRoundTrip:
    """The full computed schedule survives JSON round-trip."""

    def test_full_round_trip(self) -> None:
        schedule = _engine().compute(
            _profile(has_employees=True, pays_rent_with_retencion=True),
            2026,
            today=date(2026, 1, 1),
        )
        payload = schedule.model_dump_json()
        restored = Schedule.model_validate_json(payload)
        assert restored == schedule
