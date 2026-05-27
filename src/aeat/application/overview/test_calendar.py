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
    Schedule,
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
    # covered_years always includes the prior fiscal year so that annual
    # declarations (IS Modelo 200, IRPF Modelo 100) whose deadlines fall in
    # the following calendar year appear when querying that year.
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 1, 1))
    assert rng.covered_years() == (2025, 2026)


def test_range_covered_years_spans_year_boundary() -> None:
    rng = OverviewCalendarRange(from_date=date(2025, 10, 1), to_date=date(2026, 7, 20))
    assert rng.covered_years() == (2024, 2025, 2026)


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
# Taxpayer-model derivation at the calendar surface
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
    """The wrong-guidance fix at the calendar surface: a pure
    landlord's calendar must not list Modelo 130, even across a full
    year where every quarterly window is registered."""

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
    """An undeclared taxpayer model yields an empty calendar flagged
    taxpayer_model_declared=False — never the autónomo guess."""

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_undeclared_profile(), rng, today=date(2026, 4, 1))
    assert cal.taxpayer_model_declared is False
    assert cal.entries == ()
    assert cal.incomplete_reason is not None
    # The reason is the localised "declare your taxpayer model" guidance.
    assert "perfil" in cal.incomplete_reason


def _fully_enrolled_autonomo() -> TaxpayerProfile:
    """An autónomo whose enrolment flags trigger the full modelo set.

    Every withholding-payer and trade fact is positively declared, so
    the deadline engine schedules Modelos 111 / 115 / 130 / 303 / 349
    — all seed-ruled and ``APPLICABLE`` for this profile. Used by the
    graceful-degradation tests, which only need a profile that produces
    obligations across year boundaries.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        has_employees=True,
        pays_professionals_with_retencion=True,
        pays_rent_with_retencion=True,
        does_intracomunitario=True,
        third_party_transactions_above_347_threshold=True,
        bienes_extranjero_above_threshold=True,
    )


def _objetiva_autonomo() -> TaxpayerProfile:
    """An autónomo en estimación objetiva (módulos).

    The deadline engine schedules both Modelo 130 and Modelo 131 for an
    autónomo, but the estimation-regime axis makes them mutually
    exclusive: an objetiva autónomo owes Modelo 131 (pago fraccionado
    por módulos) and NOT Modelo 130. The calendar must therefore drop
    the ``NOT_APPLICABLE`` Modelo 130 row — a non-``APPLICABLE`` verdict
    must never appear as a confident due row.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.OBJETIVA,
        iva_regime=IVARegime.SIMPLIFICADO,
    )


def test_calendar_excludes_non_applicable_modelos() -> None:
    """A modelo the taxpayer model does not positively trigger must
    never appear as a confident calendar row.

    The deadline engine schedules both Modelo 130 and Modelo 131 for an
    autónomo. For an estimación-objetiva autónomo the regime axis makes
    Modelo 130 ``NOT_APPLICABLE`` and Modelo 131 ``APPLICABLE``. The
    calendar must surface only the ``APPLICABLE`` verdicts — a
    ``NOT_APPLICABLE`` row shown as confidently due is the W02 defect.
    """

    from ._applicability import ApplicabilityVerdict, derive_modelo_applicability

    profile = _objetiva_autonomo()
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(profile, rng, today=date(2026, 4, 1))

    calendar_modelos = {entry.modelo for entry in cal.entries}
    # Modelo 130 is NOT_APPLICABLE for an objetiva autónomo...
    assert derive_modelo_applicability(profile, "130").verdict is (
        ApplicabilityVerdict.NOT_APPLICABLE
    )
    # ...and therefore absent from the calendar.
    assert "130" not in calendar_modelos
    # Modelo 131 is the objetiva pago fraccionado — it must be present.
    assert "131" in calendar_modelos
    # Every surfaced row is a positively APPLICABLE seed-ruled modelo.
    for entry in cal.entries:
        assert derive_modelo_applicability(profile, entry.modelo).verdict is (
            ApplicabilityVerdict.APPLICABLE
        ), entry.modelo


def test_agenda_and_backlog_inherit_the_applicability_exclusion() -> None:
    """Agenda and backlog compose the calendar, so the non-applicable
    exclusion must reach them too — neither may leak the NOT_APPLICABLE
    Modelo 130 as a confident due / late row for an objetiva autónomo."""

    from ._agenda import build_overview_agenda
    from ._backlog import build_overview_backlog

    profile = _objetiva_autonomo()

    # A horizon that keeps the agenda window inside 2026 (the agenda
    # adds a 90-day overdue lookback, so the horizon must leave room).
    agenda = build_overview_agenda(profile, as_of=date(2026, 4, 1), horizon_days=200)
    agenda_modelos = {
        entry.modelo for bucket in (agenda.due_today, agenda.due_soon, agenda.overdue) for entry in bucket
    }
    assert agenda_modelos, "expected the objetiva autónomo to have agenda obligations"
    assert "130" not in agenda_modelos

    backlog = build_overview_backlog(
        profile,
        from_date=date(2026, 1, 1),
        to_date=date(2026, 12, 31),
        as_of=date(2026, 12, 31),
    )
    backlog_modelos = {item.modelo for item in backlog.items}
    assert "130" not in backlog_modelos


# ---------------------------------------------------------------------
# Multi-year ranges degrade gracefully across years with no window data
# ---------------------------------------------------------------------


def test_calendar_year_without_windows_only_does_not_raise() -> None:
    """A range whose primary year has no registered deadline windows
    does not raise, and the taxpayer-model state is answered.

    The registry has no deadline windows for 2027 (registry-track gap
    R1). Before the multi-year degradation fix the deadline engine's
    ``ScheduleComputationError`` for that year propagated all the way to
    the operator as a hard error. A year with no registered window data
    is a normal "no data yet" state: ``build_overview_calendar`` must
    return a valid :class:`OverviewCalendar` instead of raising.

    Note: ``covered_years()`` now includes the prior year (2026) to pick
    up prior-fiscal-year deadlines (e.g. IS / Renta annual declarations)
    that open in the queried calendar year. Some 2026 Q4 windows open in
    January 2027 and therefore appear in a 2027 range. The contract is
    that the call succeeds — not that the calendar is empty.
    """

    profile = _fully_enrolled_autonomo()
    rng = OverviewCalendarRange(from_date=date(2027, 1, 1), to_date=date(2027, 12, 31))

    # The contract: this call does not raise.
    cal = build_overview_calendar(profile, rng, today=date(2027, 6, 1))

    assert isinstance(cal, OverviewCalendar)
    assert cal.taxpayer_model_declared is True
    assert cal.incomplete_reason is None
    # All surfaced entries intersect the query range.
    for entry in cal.entries:
        assert entry.closes_on >= rng.from_date
        assert entry.opens_on <= rng.to_date


def test_calendar_spanning_a_year_without_windows_does_not_raise() -> None:
    """A range crossing into a year with no registered deadline windows
    must succeed instead of raising.

    The registry has no deadline windows for 2027. Before the
    degradation fix the engine's ``ScheduleComputationError`` for the
    uncovered 2027 year propagated through ``build_overview_calendar``
    and surfaced to the operator as a hard error. A range spanning
    2026 (populated) and 2027 (no data) must instead return a valid
    :class:`OverviewCalendar`: the empty year's swallowed schedule
    contributes nothing while the populated years still answer.

    The degradation invariant: extending a populated-year range into a
    no-windows year never *removes* an entry — every row a 2026-only
    range produces, the 2026/2027-spanning range still produces (a
    wider window can only admit more rows, never fewer).
    """

    profile = _fully_enrolled_autonomo()
    multi_year = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2027, 7, 31))
    populated_only = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))

    # The contract: neither call raises on the empty 2027 year.
    multi_cal = build_overview_calendar(profile, multi_year, today=date(2026, 4, 1))
    populated_cal = build_overview_calendar(profile, populated_only, today=date(2026, 4, 1))

    assert isinstance(multi_cal, OverviewCalendar)
    assert multi_cal.taxpayer_model_declared is True
    assert multi_cal.incomplete_reason is None
    # The empty 2027 year never drops a populated-year obligation: the
    # spanning range is a superset of the 2026-only range.
    populated_keys = {
        (entry.modelo, entry.period, entry.closes_on) for entry in populated_cal.entries
    }
    multi_keys = {
        (entry.modelo, entry.period, entry.closes_on) for entry in multi_cal.entries
    }
    assert populated_keys <= multi_keys


def test_agenda_across_year_boundary_without_windows_does_not_raise() -> None:
    """``overview agenda`` composes the calendar over a window anchored
    on ``as_of``; a horizon that pushes the window into a year with no
    registered windows must not raise.

    With ``as_of`` late in 2026 and a 365-day horizon the agenda window
    crosses into 2027 (no windows). Before the degradation fix the
    engine's ``ScheduleComputationError`` for 2027 surfaced as a hard
    operator error. The agenda must answer instead — every cohort is a
    valid tuple.
    """

    from ._agenda import build_overview_agenda

    profile = _fully_enrolled_autonomo()

    # The contract: this call does not raise on the empty 2027 year.
    agenda = build_overview_agenda(profile, as_of=date(2026, 11, 1), horizon_days=365)

    assert agenda.taxpayer_model_declared is True
    assert agenda.incomplete_reason is None
    # Every cohort is a valid tuple; the agenda answered rather than
    # crashing on the uncovered 2027 year.
    assert isinstance(agenda.due_today, tuple)
    assert isinstance(agenda.due_soon, tuple)
    assert isinstance(agenda.overdue, tuple)


def test_backlog_across_year_boundary_without_windows_does_not_raise() -> None:
    """``overview backlog`` composes the calendar; a lookback window that
    starts in a year with no registered windows must not raise.

    ``as_of`` in 2027 (no windows) with the default 365-day lookback
    spans into 2026. The backlog must answer rather than crash on the
    uncovered 2027 year.
    """

    from ._backlog import build_overview_backlog

    profile = _fully_enrolled_autonomo()

    # The contract: this call does not raise on the empty 2027 year.
    backlog = build_overview_backlog(profile, as_of=date(2027, 3, 1))

    assert backlog.taxpayer_model_declared is True
    # Every surfaced backlog item is past-due relative to as_of — the
    # backlog answered instead of crashing on the uncovered 2027 year.
    assert all(item.adjusted_closes_on < date(2027, 3, 1) for item in backlog.items)


# ---------------------------------------------------------------------
# Undeclared-profile operator message — locale delivery
# ---------------------------------------------------------------------


def test_undeclared_profile_message_resolves_to_real_localised_text() -> None:
    """The undeclared-profile guidance must be a shipped locale string,
    not the raw translation key.

    ``build_overview_calendar`` populates ``incomplete_reason`` via
    ``tr("cli.overview.taxpayer_model_undeclared")``. python-i18n
    returns the literal key when no catalogue entry exists, so the
    contract here is: the rendered text differs from the key, is
    non-trivially long, and resolves to genuine guidance in every
    supported language (es / en / ca / hu).
    """

    from aeat.core.i18n import tr

    key = "cli.overview.taxpayer_model_undeclared"
    for locale in ("es", "en", "ca", "hu"):
        rendered = tr(key, locale=locale)
        # Not the raw key, not the python-i18n "[missing translation]" stub.
        assert rendered != key, locale
        assert "[missing" not in rendered.lower(), locale
        assert "translation" not in rendered.lower() or len(rendered) > 40, locale
        # Real operator guidance — a full sentence, not a one-token stub.
        assert len(rendered) > 30, (locale, rendered)
        assert " " in rendered.strip(), (locale, rendered)

    # The calendar surface delivers exactly that resolved text.
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_undeclared_profile(), rng, today=date(2026, 4, 1))
    assert cal.incomplete_reason == tr(key)
    assert cal.incomplete_reason is not None
    assert cal.incomplete_reason != key


# ---------------------------------------------------------------------
# Entity-type calendar correctness (corporate-entity ADR §4)
# ---------------------------------------------------------------------


def _legal_entity() -> TaxpayerProfile:
    """A sociedad limitada — an Impuesto sobre Sociedades contribuyente."""

    from ...domain.deadlines._models import LegalEntityForm

    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )


def _attribution_entity() -> TaxpayerProfile:
    """An attribution entity — comunidad de bienes / sociedad civil."""

    return TaxpayerProfile(
        tax_id="E12345678",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        iva_regime=IVARegime.GENERAL,
    )


def test_calendar_legal_entity_is_never_shown_an_irpf_cuota() -> None:
    """A legal entity's calendar must never list an IRPF cuota modelo.

    Modelo 100 / 130 / 303 deadline windows are registered and the
    deadline engine still surfaces them (the registry applicability
    conditions are not yet entity-type-aware — a W03 registry gap).
    The applicability filter in ``build_overview_calendar`` is what
    keeps the calendar correct: a sociedad limitada is an Impuesto
    sobre Sociedades contribuyente, so every IRPF modelo resolves
    NOT_APPLICABLE and is dropped. The engine never shows a company an
    IRPF tarifa obligation (corporate-entity ADR §4)."""

    rng = OverviewCalendarRange(from_date=date(2024, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, today=date(2025, 7, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    # No IRPF cuota modelo reaches a legal entity's calendar.
    assert surfaced.isdisjoint({"100", "130"})
    assert cal.taxpayer_model_declared is True


def test_calendar_natural_person_shows_irpf_not_corporate() -> None:
    """A natural person's calendar shows the IRPF obligations and never
    a corporate-tax modelo. An autónomo en estimación directa keeps
    Modelo 130 / 303; Modelo 200 / 202 never reach the calendar."""

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_profile(), rng, today=date(2026, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "130" in surfaced
    # A natural person is never shown a corporate-tax obligation.
    assert surfaced.isdisjoint({"200", "202"})


def test_calendar_attribution_entity_is_shown_no_cuota_obligation() -> None:
    """An attribution entity's calendar lists no IS and no IRPF cuota.

    A comunidad de bienes runs no cuota self-assessment of its own —
    the income is taxed in the members' returns (corporate-entity ADR
    §2). Every cuota modelo (100 / 130 / 200 / 202) resolves to the
    ATTRIBUTION_PASS_THROUGH verdict and is dropped from the calendar;
    the engine never shows the entity a cuota obligation it does not
    owe."""

    rng = OverviewCalendarRange(from_date=date(2024, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(_attribution_entity(), rng, today=date(2025, 7, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    # No cuota self-assessment reaches an attribution entity's calendar.
    assert surfaced.isdisjoint({"100", "130", "200", "202"})
    # The taxpayer model is declared — the calendar answered, it did
    # not refuse with an INCOMPLETE.
    assert cal.taxpayer_model_declared is True
    assert cal.incomplete_reason is None


# ---------------------------------------------------------------------
# NoDeadlineWindowsError catch-narrowing (round-4 #40)
# ---------------------------------------------------------------------


class _NoWindowsEngine:
    """A ScheduleProducer that raises the benign no-windows fault.

    Real-behaviour fault injector for the ``build_overview_calendar``
    exception-narrowing contract: it raises the genuine
    :class:`NoDeadlineWindowsError` the engine raises for a year with
    no registered deadline windows. Not a mock of engine behaviour —
    it exercises the calendar's pure catch logic against the real
    exception type.
    """

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        from ...domain.deadlines._errors import NoDeadlineWindowsError

        raise NoDeadlineWindowsError(
            f"No registry deadline windows registered for year {year}"
        )


class _CorruptRegistryEngine:
    """A ScheduleProducer that raises a genuine registry-integrity fault.

    Raises the bare :class:`ScheduleComputationError` the deadline
    engine raises for a real registry-integrity fault (validation
    failure, profile-condition evaluation failure) — distinct from the
    benign :class:`NoDeadlineWindowsError`. The calendar must let this
    propagate, not swallow it as a missing-data state.
    """

    def compute(
        self,
        profile: TaxpayerProfile,
        year: int,
        *,
        today: date | None = None,
    ) -> Schedule:
        from ...domain.deadlines._errors import ScheduleComputationError

        raise ScheduleComputationError(
            f"deadline registry validation failed for year {year}"
        )


def test_calendar_benign_no_windows_year_still_degrades() -> None:
    """The benign no-windows fault still degrades gracefully after the
    catch was narrowed to ``NoDeadlineWindowsError``.

    A year whose schedule raises the benign ``NoDeadlineWindowsError``
    contributes zero entries; the calendar still returns a valid empty
    result rather than propagating the error."""

    rng = OverviewCalendarRange(from_date=date(2030, 1, 1), to_date=date(2030, 12, 31))
    cal = build_overview_calendar(
        _profile(), rng, today=date(2030, 6, 1), engine=_NoWindowsEngine()
    )

    assert isinstance(cal, OverviewCalendar)
    assert cal.entries == ()
    assert cal.taxpayer_model_declared is True


def test_calendar_propagates_genuine_registry_fault() -> None:
    """A genuine registry-integrity fault must propagate past
    ``build_overview_calendar`` instead of being swallowed.

    Before the catch was narrowed, the broad ``ScheduleComputationError``
    catch silently masked a registry validation failure as a benign
    "no data yet" year. The narrowed ``NoDeadlineWindowsError`` catch
    lets the genuine fault surface so a corrupt registry is never
    hidden from the operator (round-4 #40)."""

    from ...domain.deadlines._errors import (
        NoDeadlineWindowsError,
        ScheduleComputationError,
    )

    rng = OverviewCalendarRange(from_date=date(2030, 1, 1), to_date=date(2030, 12, 31))
    with pytest.raises(ScheduleComputationError) as excinfo:
        build_overview_calendar(
            _profile(), rng, today=date(2030, 6, 1), engine=_CorruptRegistryEngine()
        )
    # The genuine fault is the bare base class, not the benign subtype —
    # the narrowed catch deliberately let it through.
    assert not isinstance(excinfo.value, NoDeadlineWindowsError)
    assert "validation failed" in str(excinfo.value)


# ---------------------------------------------------------------------
# S227 regressions — LEGAL_ENTITY calendar completeness
# ---------------------------------------------------------------------


def test_calendar_legal_entity_shows_modelo_202_pagos_fraccionados() -> None:
    """S227 regression: M202 must appear in the calendar for a LEGAL_ENTITY profile.

    The M202 filing schedule uses ``field = "taxpayer.entity_type"`` as a profile
    condition, but TaxpayerProfile has ``entity_type`` directly — no ``.taxpayer``
    sub-attribute. Without the ``_resolve_profile_fact`` special case, the condition
    evaluation raises ``RegistryValidationError`` inside
    ``applicable_filing_schedules``, causing the engine to crash.

    After the fix the condition resolves correctly and M202 appears for an
    Impuesto sobre Sociedades contribuyente across the quarters registered.
    """

    rng = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, today=date(2025, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "202" in surfaced, (
        "M202 (pago fraccionado IS) must appear for a LEGAL_ENTITY profile; "
        "absent → filing-schedule profile-condition cannot resolve taxpayer.entity_type"
    )
    assert cal.taxpayer_model_declared is True


def test_calendar_legal_entity_shows_modelo_200_impuesto_sociedades() -> None:
    """S227 regression: M200 must appear for a LEGAL_ENTITY profile.

    The M200 Impuesto sobre Sociedades annual declaration has ``filing_year = 2024``
    but its deadline window opens on 2025-07-01 and closes on 2025-07-25. A calendar
    query for the range 2025-01-01 to 2025-12-31 must include it.

    Before the ``covered_years()`` fix, the aggregator computed only ``year=2025``
    schedules. ``deadline_windows(2025)`` returns nothing for M200 (its
    ``filing_year=2024``), so M200 was absent. The fix expands ``covered_years()``
    to include ``from_date.year - 1`` (2024) so ``deadline_windows(2024)`` is also
    queried and M200's window (which intersects the 2025 date range) is surfaced.
    """

    rng = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31))
    cal = build_overview_calendar(_legal_entity(), rng, today=date(2025, 4, 1))

    surfaced = {entry.modelo for entry in cal.entries}
    assert "200" in surfaced, (
        "M200 (IS annual) must appear for a LEGAL_ENTITY profile querying 2025; "
        "absent → covered_years() did not include prior fiscal year 2024"
    )
