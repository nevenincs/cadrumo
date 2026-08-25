"""Taxpayer-model and entity-type overview-calendar tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....adapters.outbound.aeat.sede import Declaracion
from ....core import Period
from ....domain.deadlines import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    TaxpayerProfile,
)
from ...live.expedientes import PersistedExpedientesSnapshot
from .. import (
    OverviewCalendar,
    OverviewCalendarRange,
    build_overview_calendar,
    calendar_events_from_expedientes_snapshots,
)
from .calendar_test_support import BUCKET_ID as _BUCKET_ID
from .calendar_test_support import SOURCE_URL as _SOURCE_URL
from .calendar_test_support import profile as _profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

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


def _autonomo_without_declared_regime() -> TaxpayerProfile:
    """Operator repro: actividad económica declared, no estimation regime.

    Created with ``--irpf-income-categories actividad_economica`` and no
    ``--irpf-estimation-regime`` (the wizard regime question is optional),
    so ``irpf_estimation_regime`` is ``None``. Estimación directa is the
    LIRPF default method, so this autónomo owes Modelo 130 — the calendar
    must surface its quarterly pago-fraccionado deadlines, not drop the
    one family the profile owes.
    """

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        iva_regime=IVARegime.GENERAL,
    )


def test_calendar_autonomo_without_declared_regime_shows_range_intersecting_m130_quarters() -> None:
    """Operator repro fix: an actividad-económica profile with no declared
    estimation regime owes the four Modelo 130 quarterly pago-fraccionado
    deadlines.

    The profile was created with ``--irpf-income-categories
    actividad_economica`` but no ``--irpf-estimation-regime`` (the regime
    question is optional in the setup wizard), leaving
    ``irpf_estimation_regime`` ``None``. Before the fix the applicability
    rule resolved Modelo 130 to ``INCOMPLETE`` for an undeclared regime
    and the calendar dropped every M130 row — the one deadline family this
    autónomo owes was absent. Estimación directa is the LIRPF default
    method (art. 16; RIRPF art. 32 makes módulos opt-in), so the four
    quarterly windows must now appear with the registry-grounded close
    dates.
    """

    profile = _autonomo_without_declared_regime()
    assert profile.irpf_estimation_regime is None
    # The range includes the closing 2025 4T filing window in January
    # 2026 and all four filing-year 2026 quarterly windows.
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2027, 2, 28))
    cal = build_overview_calendar(profile, rng, today=date(2026, 4, 1))

    assert cal.taxpayer_model_declared is True
    m130_entries = sorted(
        (entry for entry in cal.entries if entry.modelo == "130"),
        key=lambda entry: entry.closes_on,
    )
    # Every M130 filing window intersecting the calendar range is present.
    assert len(m130_entries) == 5, [(e.period.filing_year, e.period.registry_token, e.closes_on) for e in m130_entries]
    # The close dates are the registry deadline windows — never hand-invented.
    # (M130 deadline_windows: 2025 4T closes in January 2026; filing-year
    # 2026 contributes its 1T/2T/3T/4T windows.)
    assert [(entry.period.filing_year, entry.period.registry_token) for entry in m130_entries] == [
        (2025, "4T"),
        (2026, "1T"),
        (2026, "2T"),
        (2026, "3T"),
        (2026, "4T"),
    ]
    assert [entry.closes_on for entry in m130_entries] == [
        date(2026, 1, 30),
        date(2026, 4, 20),
        date(2026, 7, 20),
        date(2026, 10, 20),
        date(2027, 1, 30),
    ]
    # The business-day-adjusted close is never earlier than the legal close.
    for entry in m130_entries:
        assert entry.adjusted_closes_on >= entry.closes_on
    # Modelo 131 (estimación objetiva) must NOT appear — directa and
    # objetiva are mutually exclusive on the regime, and the undeclared
    # regime resolves to directa.
    assert "131" not in {entry.modelo for entry in cal.entries}


def test_calendar_pure_landlord_without_regime_owes_no_m130() -> None:
    """The directa default must not over-include a non-owing profile.

    A pure landlord (rendimientos del capital inmobiliario only, no
    actividad económica) and likewise a salaried-only / pensioner profile
    declare no economic activity, so the regime-default fallback never
    fires for Modelo 130: it stays excluded from the calendar. The fix
    adds M130 only for profiles that genuinely owe it.
    """

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2027, 2, 28))
    cal = build_overview_calendar(_landlord_profile(), rng, today=date(2026, 4, 1))
    assert "130" not in {entry.modelo for entry in cal.entries}


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


def test_calendar_undeclared_profile_preserves_observed_events() -> None:
    """Observed AEAT events remain visible even when obligations cannot be derived."""

    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    events = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="e" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2026, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2026,
                        period=Period.from_year_and_code(2026, "1T"),
                        expediente_id="202630313520389Q",
                        estado="ALTA",
                        presented_at=datetime(2026, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2026, 4, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        rng,
    )

    cal = build_overview_calendar(_undeclared_profile(), rng, today=date(2026, 4, 1), events=events)

    assert cal.taxpayer_model_declared is False
    assert cal.entries == ()
    assert tuple(event.reference_id for event in cal.events) == ("202630313520389Q",)


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
    ``NOT_APPLICABLE`` row shown as confidently due is the regression defect.
    """

    from cadrumo.domain.calculations.registry.applicability import ApplicabilityVerdict, derive_modelo_applicability

    profile = _objetiva_autonomo()
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
    cal = build_overview_calendar(profile, rng, today=date(2026, 4, 1))

    calendar_modelos = {entry.modelo for entry in cal.entries}
    # Modelo 130 is NOT_APPLICABLE for an objetiva autónomo...
    assert derive_modelo_applicability(profile, "130").verdict is (ApplicabilityVerdict.NOT_APPLICABLE)
    # ...and therefore absent from the calendar.
    assert "130" not in calendar_modelos
    # Modelo 131 is the objetiva pago fraccionado — it must be present.
    assert "131" in calendar_modelos
    # Every surfaced row is a positively APPLICABLE seed-ruled modelo.
    for entry in cal.entries:
        assert derive_modelo_applicability(profile, entry.modelo).verdict is (ApplicabilityVerdict.APPLICABLE), (
            entry.modelo
        )


def test_agenda_and_backlog_inherit_the_applicability_exclusion() -> None:
    """Agenda and backlog compose the calendar, so the non-applicable
    exclusion must reach them too — neither may leak the NOT_APPLICABLE
    Modelo 130 as a confident due / late row for an objetiva autónomo."""

    from .._agenda import build_overview_agenda
    from .._backlog import build_overview_backlog

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
    populated_keys = {(entry.modelo, entry.period, entry.closes_on) for entry in populated_cal.entries}
    multi_keys = {(entry.modelo, entry.period, entry.closes_on) for entry in multi_cal.entries}
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

    from .._agenda import build_overview_agenda

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

    from .._backlog import build_overview_backlog

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

    from ....core.i18n import tr

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
# Entity-type calendar correctness (corporate-entity contract §4)
# ---------------------------------------------------------------------


def _legal_entity() -> TaxpayerProfile:
    """A sociedad limitada — an Impuesto sobre Sociedades contribuyente."""

    from ....domain.deadlines import LegalEntityForm

    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
    )


def _attribution_entity() -> TaxpayerProfile:
    """An attribution entity — comunidad de bienes / sociedad civil."""

    return TaxpayerProfile(
        tax_id="E12345674",
        entity_type=EntityType.ATTRIBUTION_ENTITY,
        iva_regime=IVARegime.GENERAL,
    )


def test_calendar_legal_entity_is_never_shown_an_irpf_cuota() -> None:
    """A legal entity's calendar must never list an IRPF cuota modelo.

    Modelo 100 / 130 / 303 deadline windows are registered and the
    deadline engine still surfaces them (the registry applicability
    conditions are not yet entity-type-aware — a registry gap).
    The applicability filter in ``build_overview_calendar`` is what
    keeps the calendar correct: a sociedad limitada is an Impuesto
    sobre Sociedades contribuyente, so every IRPF modelo resolves
    NOT_APPLICABLE and is dropped. The engine never shows a company an
    IRPF tarifa obligation (corporate-entity contract §4)."""

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


def test_calendar_suppresses_modelo_721_without_crypto_abroad_threshold() -> None:
    """A default foreign-asset false profile must not receive active M721 rows."""

    profile = TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
        bienes_extranjero_above_threshold=False,
        monedas_virtuales_extranjero_above_threshold=False,
    )
    rng = OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 3, 31))

    cal = build_overview_calendar(profile, rng, today=date(2025, 1, 15), show_suppressed=True)

    assert "721" not in {entry.modelo for entry in cal.entries}
    suppressed_721 = [entry for entry in cal.suppressed_entries if entry.modelo == "721"]
    assert suppressed_721
    assert {entry.verdict.value for entry in suppressed_721} == {"incomplete"}


def test_calendar_attribution_entity_is_shown_no_cuota_obligation() -> None:
    """An attribution entity's calendar lists no IS and no IRPF cuota.

    A comunidad de bienes runs no cuota self-assessment of its own —
    the income is taxed in the members' returns (corporate-entity contract
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
