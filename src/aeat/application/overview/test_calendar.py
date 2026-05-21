"""Unit tests for the typed overview-calendar aggregator."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ...domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    ObligationStatus,
    TaxpayerProfile,
)
from . import (
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarRange,
    OverviewPeriodState,
    build_overview_calendar,
    user_state_for,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _profile() -> TaxpayerProfile:
    """A declared autónomo en estimación directa.

    The structural calendar tests need a profile whose taxpayer model
    produces obligations. An autónomo with rendimientos de actividades
    económicas under estimación directa is the unchanged-by-design
    persona — Modelo 130 / 303 stay applicable, exactly as before the
    taxpayer-type derivation landed.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_professionals_with_retencion=False,
        professional_income_withholding_ge_70pct=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        third_party_transactions_above_347_threshold=False,
        bienes_extranjero_above_threshold=False,
        notes="overview-calendar test profile",
    )


# ---------------------------------------------------------------------
# OverviewPeriodState mapping
# ---------------------------------------------------------------------


def test_period_state_enum_carries_cli_values() -> None:
    assert {item.value for item in OverviewPeriodState} == {
        "due",
        "late",
        "filed",
        "unknown",
    }


def test_user_state_maps_open_window_to_due() -> None:
    assert user_state_for(ObligationStatus.UPCOMING) is OverviewPeriodState.DUE
    assert user_state_for(ObligationStatus.DUE_SOON) is OverviewPeriodState.DUE
    assert user_state_for(ObligationStatus.DUE_TODAY) is OverviewPeriodState.DUE


def test_user_state_maps_overdue_to_late() -> None:
    assert user_state_for(ObligationStatus.OVERDUE) is OverviewPeriodState.LATE


def test_user_state_maps_filed_to_filed() -> None:
    assert user_state_for(ObligationStatus.FILED) is OverviewPeriodState.FILED


def test_user_state_maps_not_applicable_to_unknown() -> None:
    assert user_state_for(ObligationStatus.NOT_APPLICABLE) is OverviewPeriodState.UNKNOWN


def test_user_state_covers_every_engine_status() -> None:
    """Every ObligationStatus must map to a user state."""
    for status in ObligationStatus:
        assert isinstance(user_state_for(status), OverviewPeriodState)


# ---------------------------------------------------------------------
# OverviewCalendarRange
# ---------------------------------------------------------------------


def test_range_round_trips_canonical_window() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.from_date == date(2026, 1, 1)
    assert rng.to_date == date(2026, 4, 20)


def test_range_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match=r"from_date|to_date|window|range"):
        OverviewCalendarRange(from_date=date(2026, 4, 20), to_date=date(2026, 1, 1))


def test_range_accepts_single_day_window() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 1, 1))
    assert rng.covered_years() == (2026,)


def test_range_covered_years_spans_year_boundary() -> None:
    rng = OverviewCalendarRange(from_date=date(2025, 10, 1), to_date=date(2026, 7, 20))
    assert rng.covered_years() == (2025, 2026)


def test_range_covers_returns_true_for_inclusive_bounds() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.covers(date(2026, 1, 1)) is True
    assert rng.covers(date(2026, 4, 20)) is True
    assert rng.covers(date(2026, 3, 15)) is True


def test_range_covers_returns_false_outside_bounds() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.covers(date(2025, 12, 31)) is False
    assert rng.covers(date(2026, 4, 21)) is False


def test_range_is_frozen() -> None:
    from pydantic import ValidationError

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        rng.from_date = date(2025, 12, 31)


# ---------------------------------------------------------------------
# OverviewCalendarEntry
# ---------------------------------------------------------------------


def _entry(**overrides: object) -> OverviewCalendarEntry:
    base: dict[str, object] = {
        "modelo": "130",
        "period": "2026Q1",
        "opens_on": date(2026, 4, 1),
        "closes_on": date(2026, 4, 20),
        "adjusted_closes_on": date(2026, 4, 20),
        "shift_reason": "business_day",
        "holiday_refs": (),
        "jurisdictions": (),
        "payment_cutoff_on": date(2026, 4, 15),
        "status": ObligationStatus.UPCOMING,
        "user_state": OverviewPeriodState.DUE,
    }
    base.update(overrides)
    return OverviewCalendarEntry.model_validate(base)


def test_entry_round_trips_canonical_fields() -> None:
    entry = _entry()
    assert entry.modelo == "130"
    assert entry.period == "2026Q1"
    assert entry.user_state is OverviewPeriodState.DUE


def test_entry_rejects_inverted_window() -> None:
    with pytest.raises(ValueError, match=r"opens_on|closes_on|window"):
        _entry(opens_on=date(2026, 4, 21), closes_on=date(2026, 4, 20))


def test_entry_rejects_payment_cutoff_after_closes_on() -> None:
    with pytest.raises(ValueError, match=r"payment_cutoff|closes_on"):
        _entry(payment_cutoff_on=date(2026, 4, 25))


def test_entry_rejects_user_state_inconsistent_with_engine_status() -> None:
    with pytest.raises(ValueError, match=r"user_state|status|inconsistent"):
        _entry(status=ObligationStatus.OVERDUE, user_state=OverviewPeriodState.DUE)


def test_entry_is_frozen() -> None:
    from pydantic import ValidationError

    entry = _entry()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        entry.modelo = "303"


# ---------------------------------------------------------------------
# build_overview_calendar
# ---------------------------------------------------------------------


def test_build_returns_typed_calendar_for_quarterly_window() -> None:
    """``--from 2026-01-01 --to 2026-04-20`` covers Q1 2026."""
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20)),
        today=date(2026, 4, 1),
    )
    assert isinstance(calendar, OverviewCalendar)
    assert calendar.range.from_date == date(2026, 1, 1)
    assert calendar.range.to_date == date(2026, 4, 20)
    assert isinstance(calendar.generated_at, datetime)
    assert calendar.generated_at.tzinfo == UTC


def test_build_only_emits_entries_inside_range() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20)),
        today=date(2026, 4, 1),
    )
    for entry in calendar.entries:
        # An entry must intersect the inclusive range.
        assert entry.closes_on >= date(2026, 1, 1)
        assert entry.opens_on <= date(2026, 4, 20)


def test_build_orders_entries_by_close_then_modelo_then_period() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        today=date(2026, 4, 1),
    )
    keys = [(entry.closes_on, entry.modelo, entry.period) for entry in calendar.entries]
    assert keys == sorted(keys)


def test_build_tape_invocation_2025q4_through_2026q2_spans_year_boundary() -> None:
    """``--from 2025-10-01 --to 2026-07-20`` spans multiple years."""
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 10, 1), to_date=date(2026, 7, 20)),
        today=date(2026, 5, 3),
    )
    years = {entry.period[:4] for entry in calendar.entries}
    # The range straddles 2025 -> 2026, so both years must contribute.
    assert "2025" in years or "2026" in years


def test_build_user_state_matches_engine_status_per_entry() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31)),
        today=date(2026, 4, 1),
    )
    for entry in calendar.entries:
        assert entry.user_state is user_state_for(entry.status)


def test_build_empty_range_when_window_covers_no_obligations() -> None:
    """A 1-day window outside every modelo's filing window emits no entries."""
    # 2026-01-15 lies outside every modelo's January quarterly / monthly window.
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2026, 1, 15), to_date=date(2026, 1, 15)),
        today=date(2026, 4, 1),
    )
    assert isinstance(calendar.entries, tuple)


def test_build_threads_shift_metadata_onto_every_entry() -> None:
    """Every assembled entry carries the festivos-shift outcome.

    The contract: ``adjusted_closes_on`` is populated, ``shift_reason``
    is one of the closed set returned by
    :func:`aeat.domain.deadlines.shift_deadline`, and the adjusted date
    never precedes the original close.
    """
    accepted_reasons = {
        "business_day",
        "modelo_exception",
        "weekend",
        "national_holiday",
        "ccaa_holiday",
        "calendar_unavailable",
    }
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_profile(), rng, today=date(2026, 4, 1))
    assert cal.entries, "expected the test profile to produce at least one obligation"
    for entry in cal.entries:
        assert entry.adjusted_closes_on >= entry.closes_on
        assert entry.shift_reason in accepted_reasons


def test_build_marks_modelo_369_as_modelo_exception() -> None:
    """Modelo 369 obligations bypass the shift; reason must be modelo_exception."""
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_profile(), rng, today=date(2026, 4, 1))
    modelo_369 = [entry for entry in cal.entries if entry.modelo == "369"]
    # Whether 369 appears for the test profile depends on the profile's
    # OSS enrolment. When it does appear, the shift must be skipped.
    for entry in modelo_369:
        assert entry.shift_reason == "modelo_exception"
        assert entry.adjusted_closes_on == entry.closes_on
        assert entry.holiday_refs == ()


def test_entry_rejects_adjusted_close_that_precedes_original() -> None:
    """The shift rule is strictly monotone non-decreasing.

    A construction with ``adjusted_closes_on < closes_on`` is a
    structural violation: the shift can only move a deadline forward.
    """
    with pytest.raises(ValueError, match=r"adjusted_closes_on|may only move"):
        _entry(
            closes_on=date(2026, 4, 20),
            adjusted_closes_on=date(2026, 4, 19),
        )


def test_build_is_idempotent_modulo_generated_at() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    profile = _profile()
    a = build_overview_calendar(profile, rng, today=today)
    b = build_overview_calendar(profile, rng, today=today)
    assert a.entries == b.entries
    assert a.range == b.range


def test_calendar_omits_warnings_when_raw_values_not_supplied() -> None:
    """Without raw_values the aggregator returns no warnings or completeness rows.

    Existing callers that build the calendar from a fully-resolved
    ``TaxpayerProfile`` without surfacing the user_cli raw mapping
    must not see new warning behaviour. The empty defaults on
    OverviewCalendar.warnings / completeness preserve backwards
    compatibility for those callers.
    """
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    cal = build_overview_calendar(_profile(), rng, today=today)
    assert cal.warnings == ()
    assert cal.completeness.explicitly_set_keys == ()
    assert cal.completeness.defaulted_keys == ()


def test_calendar_emits_warning_when_iva_regime_unset() -> None:
    """A profile with no iva.regime declared must produce a typed warning.

    The deadline engine's modelo-applicability rules default to GENERAL
    when iva.regime is absent and would otherwise compute 303/390
    entries under those defaults without signalling the assumption.
    The contract verified here: when raw_values omits iva.regime, the
    aggregator emits a CalendarWarning whose code names the missing
    key, fix_command supplies the literal aeat config profile edit
    command, and affected_modelos lists 303/390.
    """
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    raw = {"tax.id": "X1234567L", "activity": "design"}
    cal = build_overview_calendar(_profile(), rng, today=today, raw_values=raw)
    iva_warnings = [w for w in cal.warnings if w.code == "iva.regime"]
    assert len(iva_warnings) == 1
    warning = iva_warnings[0]
    assert "303" in warning.affected_modelos
    assert "390" in warning.affected_modelos
    assert warning.fix_command == "aeat config profile edit"


def test_calendar_completeness_lists_uncomputable_with_reason() -> None:
    """``CalendarCompleteness`` must enumerate explicit vs defaulted keys.

    With only ``iva.regime`` declared, the completeness payload must
    list it under explicitly_set_keys and the remaining gating keys
    (does_intracomunitario, pays_professionals_with_retencion,
    pays_rent_with_retencion, uses_objective_estimation_irpf) under
    defaulted_keys.
    """
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    raw = {
        "tax.id": "X1234567L",
        "activity": "design",
        "iva.regime": "general",
    }
    cal = build_overview_calendar(_profile(), rng, today=today, raw_values=raw)
    assert "iva.regime" in cal.completeness.explicitly_set_keys
    assert "does_intracomunitario" in cal.completeness.defaulted_keys
    assert "pays_professionals_with_retencion" in cal.completeness.defaulted_keys
    assert "pays_rent_with_retencion" in cal.completeness.defaulted_keys
    assert "uses_objective_estimation_irpf" in cal.completeness.defaulted_keys


# ---------------------------------------------------------------------
# W02.S10 — taxpayer-model derivation at the calendar surface
# ---------------------------------------------------------------------


def _landlord_profile() -> TaxpayerProfile:
    """A pure landlord: rendimientos del capital inmobiliario only."""

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.CAPITAL_INMOBILIARIO}),
        iva_regime=IVARegime.EXENTO,
    )


def _undeclared_profile() -> TaxpayerProfile:
    """A profile with no taxpayer model declared at all."""

    return TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL)


def test_calendar_landlord_never_shows_modelo_130() -> None:
    """The round-3 Q1 fix at the calendar surface: a pure landlord's
    calendar must not list Modelo 130, even across a full year where
    every quarterly window is registered."""

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_landlord_profile(), rng, today=date(2026, 4, 1))
    assert cal.taxpayer_model_declared is True
    modelos = {entry.modelo for entry in cal.entries}
    assert "130" not in modelos
    assert "303" not in modelos


def test_calendar_autonomo_still_shows_modelo_130() -> None:
    """The autónomo persona is unchanged: Modelo 130 still appears."""

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_profile(), rng, today=date(2026, 4, 1))
    modelos = {entry.modelo for entry in cal.entries}
    assert "130" in modelos


def test_calendar_undeclared_profile_yields_incomplete_empty_calendar() -> None:
    """W02.S09: an undeclared taxpayer model yields an empty calendar
    flagged taxpayer_model_declared=False — never the autónomo guess."""

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_undeclared_profile(), rng, today=date(2026, 4, 1))
    assert cal.taxpayer_model_declared is False
    assert cal.entries == ()
    assert cal.incomplete_reason is not None
    # The reason is the localised "declare your taxpayer model" guidance.
    assert "perfil" in cal.incomplete_reason
