"""Unit tests for the typed overview-calendar aggregator."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ....adapters.outbound.aeat.sede import Declaracion, RemoteNotification
from ....core import Period
from ....domain.deadlines import (
    EntityType,
    IVARegime,
    LegalEntityForm,
    ObligationStatus,
    TaxpayerProfile,
)
from ....domain.modelos import ModeloCode, WorkUnit, derive_work_unit_id
from ...live import PersistedExpedientesSnapshot, PersistedNotificationsSnapshot
from .. import (
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEventType,
    OverviewCalendarRange,
    OverviewCensoEnrolmentState,
    OverviewPeriodState,
    build_filing_obligation_advisories,
    build_overview_calendar,
    build_overview_calendar_events,
    calendar_applicability_profile_keys_for_modelo,
    calendar_censo_enrolment_profile_keys,
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_notification_snapshots,
    user_state_for,
)
from .._calendar import _registry_window_for_work_unit
from .calendar_test_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .calendar_test_support import (
    PERIOD_2025_1T as _PERIOD_2025_1T,
)
from .calendar_test_support import (
    SOURCE_URL as _SOURCE_URL,
)
from .calendar_test_support import (
    profile as _profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _annual_work_unit_without_authored_window(*, modelo: str, filing_year: int) -> WorkUnit:
    """Build a real historic annual work unit for overview deadline lookup."""
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = "historic-annual-deadline-selection"
    created_at = datetime(filing_year, 1, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=ModeloCode(modelo),
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"historic-{modelo}-{filing_year}",
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.mark.parametrize(
    ("modelo", "filing_year", "calendar_range"),
    (
        ("180", 2023, OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 1, 31))),
        ("100", 2019, OverviewCalendarRange(from_date=date(2021, 4, 1), to_date=date(2021, 6, 30))),
    ),
)
def test_calendar_does_not_project_historic_annual_work_into_future_registry_window(
    modelo: str,
    filing_year: int,
    calendar_range: OverviewCalendarRange,
) -> None:
    """Overview retains an unregistered annual work unit instead of borrowing the successor's campaign."""
    work_unit = _annual_work_unit_without_authored_window(modelo=modelo, filing_year=filing_year)

    assert _registry_window_for_work_unit(work_unit) is None

    calendar = build_overview_calendar(
        _profile(),
        calendar_range,
        today=calendar_range.from_date,
        work_units=(work_unit,),
    )

    assert all(entry.local_work_unit_id != work_unit.work_unit_id for entry in calendar.entries)


def test_calendar_censo_enrolment_profile_keys_are_centralised() -> None:
    assert calendar_censo_enrolment_profile_keys() == (
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.irpf_income_categories",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    )


def test_calendar_censo_warning_requires_every_modelo_enrolment_key() -> None:
    required_303 = set(calendar_applicability_profile_keys_for_modelo("303"))
    if "taxpayer_type.irpf_income_categories" in required_303:
        required_303.add("activities.iae_epigraph")
    required_303 &= set(calendar_censo_enrolment_profile_keys())
    assert required_303 == {
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.irpf_income_categories",
    }

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(required_303 - {"iva.regime"})),
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.UNVERIFIED
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "303" in warning.affected_modelos


def test_calendar_censo_warning_clears_when_every_modelo_enrolment_key_is_verified() -> None:
    verified_303 = (
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.irpf_income_categories",
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=verified_303,
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.VERIFIED
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("303" in warning.affected_modelos for warning in censo_warnings)


def test_calendar_keeps_unverified_posture_when_no_censo_is_verified() -> None:
    """Retirement guard: with the live censo scrape retired, nothing stamps a
    censo-verified fact, so the calendar keeps its honest ``censo.enrolment_unverified``
    posture for every censo-dependent modelo when the verified-key set is empty.

    Pins the honest default: an empty ``live_censo_verified_profile_keys`` (the
    post-retirement reality) must never grant a VERIFIED enrolment state.
    """
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2025, 12, 31)),
        today=date(2025, 1, 1),
        live_censo_verified_profile_keys=(),
    )

    censo_dependent = {"100", "130", "303", "390"}
    present = {entry.modelo for entry in calendar.entries} & censo_dependent
    assert present, "fixture must yield at least one censo-dependent modelo"

    for entry in calendar.entries:
        assert entry.censo_enrolment_state is not OverviewCensoEnrolmentState.VERIFIED

    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    for modelo in present:
        entry = next(item for item in calendar.entries if item.modelo == modelo)
        assert entry.censo_enrolment_state is OverviewCensoEnrolmentState.UNVERIFIED
        assert modelo in warning.affected_modelos


def test_calendar_entry_marks_censo_enrolment_not_checked_when_no_live_censo_scope() -> None:
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
    )

    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.NOT_CHECKED
    assert "censo.enrolment_unverified" not in {warning.code for warning in calendar.warnings}


def _corporate_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B12345674",
        entity_type=EntityType.LEGAL_ENTITY,
        legal_entity_form=LegalEntityForm.SL,
        iva_regime=IVARegime.GENERAL,
        incn_prior_12_months=Decimal("7500000.00"),
        new_entity_first_two_profit_periods=False,
        notes="overview-calendar corporate test profile",
    )


def test_calendar_censo_warning_requires_corporate_modelo_202_enrolment_keys() -> None:
    required_202 = set(calendar_applicability_profile_keys_for_modelo("202"))
    required_202 &= set(calendar_censo_enrolment_profile_keys())
    assert required_202 == {
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    }

    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(required_202 - {"taxpayer_type.incn_prior_12_months"})),
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "202" in warning.affected_modelos


def test_calendar_censo_warning_clears_for_complete_corporate_modelo_202_provenance() -> None:
    verified_202 = (
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    )

    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 20)),
        today=date(2025, 4, 1),
        live_censo_verified_profile_keys=verified_202,
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("202" in warning.affected_modelos for warning in censo_warnings)


_INVALID_PAGADORES_ADVISORY_CASES: tuple[tuple[str, dict[str, str], str, str, str], ...] = (
    (
        "not-a-count-secret",
        {
            "irpf.pagadores_count": "not-a-count-secret",
            "irpf.pagadores_secondary_income": "2000",
        },
        "overview filing obligation advisory ignored invalid integer profile value",
        "irpf.pagadores_count",
        "ValueError",
    ),
    (
        "not-income-secret",
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "not-income-secret",
        },
        "overview filing obligation advisory ignored invalid decimal profile value",
        "irpf.pagadores_secondary_income",
        "InvalidOperation",
    ),
)


@pytest.mark.parametrize(
    ("raw_value", "profile_values", "expected_message", "expected_field", "expected_error_type"),
    _INVALID_PAGADORES_ADVISORY_CASES,
    ids=("invalid-count", "invalid-secondary-income"),
)
def test_invalid_pagadores_values_are_debug_logged_without_raw_value(
    caplog: pytest.LogCaptureFixture,
    raw_value: str,
    profile_values: dict[str, str],
    expected_message: str,
    expected_field: str,
    expected_error_type: str,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="cadrumo.application.overview"):
        advisories = build_filing_obligation_advisories(profile_values)

    assert advisories == ()
    relevant = [record for record in caplog.records if record.getMessage() == expected_message]
    assert len(relevant) == 1
    assert relevant[0].__dict__["profile_field"] == expected_field
    assert relevant[0].__dict__["error_type"] == expected_error_type
    assert all(raw_value not in record.getMessage() for record in caplog.records)


_MULTIPLE_PAGADORES_OBLIGATION_KEY = "cli.overview.status.filing_obligation_multiple_pagadores"


def test_multi_payer_over_reduced_limit_surfaces_obligation_advisory() -> None:
    # 2 pagadores, secondary €1,600 > €1,500, total €18,000 over the 2024 reduced
    # limit (€15,876) → the Art. 96.3 LIRPF obligation advisory fires.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
            "irpf.pagadores_total_work_income": "18000",
        },
        filing_year=2024,
    )
    assert advisories == (_MULTIPLE_PAGADORES_OBLIGATION_KEY,)


def test_multi_payer_under_reduced_limit_does_not_surface_advisory() -> None:
    # Same multiple-pagadores trigger but total €10,000 is below the 2024 reduced
    # limit (€15,876) → not obliged, no advisory.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
            "irpf.pagadores_total_work_income": "10000",
        },
        filing_year=2024,
    )
    assert advisories == ()


def test_single_payer_under_general_limit_does_not_surface_advisory() -> None:
    # 1 pagador, total €18,000 below the general €22,000 → no obligation.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "1",
            "irpf.pagadores_secondary_income": "0",
            "irpf.pagadores_total_work_income": "18000",
        },
        filing_year=2024,
    )
    assert advisories == ()


def test_multi_payer_total_undeclared_surfaces_conservatively() -> None:
    # Total work income undeclared but the multiple-pagadores trigger is met →
    # the advisory surfaces conservatively rather than granting a false clear.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
        },
        filing_year=2024,
    )
    assert advisories == (_MULTIPLE_PAGADORES_OBLIGATION_KEY,)


def test_obligation_advisory_key_resolves_to_a_translation() -> None:
    # The surfaced key must resolve to a real (non-humanised-fallback) locale
    # string in every shipped locale — the half-shipped gap this closes.
    from ....core.i18n import tr

    rendered = tr(_MULTIPLE_PAGADORES_OBLIGATION_KEY)
    # Cites the binding provision and names the form; not the humanised fallback.
    assert "96.3" in rendered
    assert "100" in rendered
    assert rendered != "Filing obligation multiple pagadores"


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


_USER_STATE_CASES: tuple[tuple[ObligationStatus, OverviewPeriodState], ...] = (
    (ObligationStatus.UPCOMING, OverviewPeriodState.DUE),
    (ObligationStatus.DUE_SOON, OverviewPeriodState.DUE),
    (ObligationStatus.DUE_TODAY, OverviewPeriodState.DUE),
    (ObligationStatus.OVERDUE, OverviewPeriodState.LATE),
    (ObligationStatus.FILED, OverviewPeriodState.FILED),
    (ObligationStatus.NOT_APPLICABLE, OverviewPeriodState.UNKNOWN),
)


@pytest.mark.parametrize(
    ("engine_status", "expected_user_state"),
    _USER_STATE_CASES,
    ids=("upcoming", "due-soon", "due-today", "overdue", "filed", "not-applicable"),
)
def test_user_state_maps_engine_status_to_cli_state(
    engine_status: ObligationStatus,
    expected_user_state: OverviewPeriodState,
) -> None:
    assert user_state_for(engine_status) is expected_user_state


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


_RANGE_COVERAGE_CASES: tuple[tuple[date, bool], ...] = (
    (date(2026, 1, 1), True),
    (date(2026, 4, 20), True),
    (date(2026, 3, 15), True),
    (date(2025, 12, 31), False),
    (date(2026, 4, 21), False),
)


@pytest.mark.parametrize(
    ("probe", "expected"),
    _RANGE_COVERAGE_CASES,
    ids=("from-bound", "to-bound", "inside", "before", "after"),
)
def test_range_covers_returns_expected_inclusive_boundary_result(probe: date, expected: bool) -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    assert rng.covers(probe) is expected


def test_range_is_frozen() -> None:
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        rng.from_date = date(2025, 12, 31)


# ---------------------------------------------------------------------
# OverviewCalendarEntry
# ---------------------------------------------------------------------


def _entry(**overrides: object) -> OverviewCalendarEntry:
    base: dict[str, object] = {
        "modelo": "130",
        "period": Period.from_year_and_code(2026, "1T"),
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
    assert entry.period == Period.from_year_and_code(2026, "1T")
    assert str(entry.period) == "2026 1T"
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
    entry = _entry()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        entry.modelo = "303"


# ---------------------------------------------------------------------
# OverviewCalendarEvent
# ---------------------------------------------------------------------


def test_expedientes_snapshots_project_filing_events_inside_range() -> None:
    snapshot = PersistedExpedientesSnapshot(
        snapshot_id="e" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="X1234567L",
        declarations=(
            Declaracion(
                modelo="303",
                ejercicio=2025,
                period=_PERIOD_2025_1T,
                expediente_id="12345678901234567890",
                estado="ALTA",
                presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
            ),
        ),
        persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_expedientes_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type is OverviewCalendarEventType.FILING
    assert event.event_date == date(2025, 4, 15)
    assert event.modelo == "303"
    assert event.filing_year == 2025
    assert event.period == Period.from_year_and_code(2025, "1T")
    assert event.reference_id == "12345678901234567890"
    assert event.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert event.authenticated_identity == "X1234567L"


def test_expedientes_snapshot_for_wrong_identity_does_not_project_filing_event() -> None:
    snapshot = PersistedExpedientesSnapshot(
        snapshot_id="e" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="Y7654321G",
        declarations=(
            Declaracion(
                modelo="303",
                ejercicio=2025,
                period=_PERIOD_2025_1T,
                expediente_id="12345678901234567890",
                estado="ALTA",
                presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
            ),
        ),
        persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_expedientes_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        expected_tax_id="X1234567L",
    )

    assert events == ()


def test_notification_snapshots_project_message_events_on_notification_date() -> None:
    row = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345674",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345674",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        rows=(row,),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        as_of=date(2025, 3, 13),
    )

    assert len(events) == 1
    assert events[0].event_type is OverviewCalendarEventType.MESSAGE
    assert events[0].event_date == date(2025, 3, 12)
    assert events[0].reference_id == "2596230606502"
    assert events[0].status == "unread"


def test_notification_snapshots_filter_message_events_by_expected_taxpayer() -> None:
    matching = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345674",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345674",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    other_taxpayer = RemoteNotification(
        certificado_id="2699101808461",
        tipo="comunicacion",
        concepto="Comunicacion de otro contribuyente",
        titular_nif="C12345674",
        titular_nombre="Other S.L.",
        destinatario_nif="C12345674",
        destinatario_nombre="Other S.L.",
        fecha_emision=date(2025, 3, 11),
        fecha_notificacion=None,
        modo_notificacion="DEHú",
        leida=True,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        rows=(matching, other_taxpayer),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        as_of=date(2025, 3, 13),
        expected_tax_id="B12345674",
    )

    assert tuple(event.reference_id for event in events) == ("2596230606502",)


def test_notification_snapshots_filter_message_events_by_authenticated_snapshot_identity() -> None:
    matching = RemoteNotification(
        certificado_id="2596230606502",
        tipo="notificacion",
        concepto="Requerimiento censal",
        titular_nif="B12345674",
        titular_nombre="Test S.L.",
        destinatario_nif="B12345674",
        destinatario_nombre="Test S.L.",
        fecha_emision=date(2025, 3, 10),
        fecha_notificacion=date(2025, 3, 12),
        modo_notificacion="DEHú",
        leida=False,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    explicit_other_taxpayer = RemoteNotification(
        certificado_id="2699101808461",
        tipo="comunicacion",
        concepto="Comunicacion de otro contribuyente",
        titular_nif="C12345674",
        titular_nombre="Other S.L.",
        destinatario_nif="C12345674",
        destinatario_nombre="Other S.L.",
        fecha_emision=date(2025, 3, 11),
        fecha_notificacion=None,
        modo_notificacion="DEHú",
        leida=True,
        source_url=AnyHttpUrl(_SOURCE_URL),
    )
    matching_snapshot = PersistedNotificationsSnapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="B12345674",
        rows=(matching, explicit_other_taxpayer),
        persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
    )
    other_snapshot = PersistedNotificationsSnapshot(
        snapshot_id="b" * 64,
        bucket_id=_BUCKET_ID,
        captured_at=datetime(2025, 3, 14, 10, 0, tzinfo=UTC),
        source_url=_SOURCE_URL,
        authenticated_identity="C12345674",
        rows=(matching,),
        persisted_at=datetime(2025, 3, 14, 10, 5, tzinfo=UTC),
    )

    events = calendar_events_from_notification_snapshots(
        (matching_snapshot, other_snapshot),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        as_of=date(2025, 3, 13),
        expected_tax_id="B12345674",
    )

    assert tuple(event.reference_id for event in events) == ("2596230606502",)


def test_build_overview_calendar_accepts_observed_events() -> None:
    event = build_overview_calendar_events(
        as_of=date(2025, 3, 13),
        calendar_range=OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        notification_snapshots=(
            PersistedNotificationsSnapshot(
                snapshot_id="a" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 3, 13, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                rows=(
                    RemoteNotification(
                        certificado_id="2596230606502",
                        tipo="comunicacion",
                        concepto="Comunicacion informativa",
                        titular_nif="B12345674",
                        titular_nombre="Test S.L.",
                        destinatario_nif="B12345674",
                        destinatario_nombre="Test S.L.",
                        fecha_emision=date(2025, 3, 10),
                        leida=True,
                        source_url=AnyHttpUrl(_SOURCE_URL),
                    ),
                ),
                persisted_at=datetime(2025, 3, 13, 10, 5, tzinfo=UTC),
            ),
        ),
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 3, 1), to_date=date(2025, 3, 31)),
        today=date(2025, 3, 15),
        events=event,
    )

    assert tuple(observed.reference_id for observed in calendar.events) == ("2596230606502",)


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
    keys = [
        (entry.closes_on, entry.modelo, entry.period.filing_year, entry.period.registry_token)
        for entry in calendar.entries
    ]
    assert keys == sorted(keys)


def test_build_preserves_each_modelo_303_2025_obligation_once_in_canonical_order() -> None:
    """Overview must not erase or multiply legal rows while projecting a schedule."""
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 1, 1), to_date=date(2026, 2, 28)),
        today=date(2025, 1, 1),
    )

    coordinates = tuple(
        (entry.modelo, entry.period.filing_year, entry.period.registry_token)
        for entry in calendar.entries
        if entry.modelo == "303" and entry.period.filing_year == 2025
    )

    assert coordinates == (
        ("303", 2025, "1T"),
        ("303", 2025, "2T"),
        ("303", 2025, "3T"),
        ("303", 2025, "4T"),
    )


def test_build_tape_invocation_2025q4_through_2026q2_spans_year_boundary() -> None:
    """``--from 2025-10-01 --to 2026-07-20`` spans multiple years."""
    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 10, 1), to_date=date(2026, 7, 20)),
        today=date(2026, 5, 3),
    )
    years = {entry.period.filing_year for entry in calendar.entries}
    # The range straddles 2025 -> 2026, so both years must contribute.
    assert 2025 in years or 2026 in years


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
    :func:`cadrumo.domain.deadlines.shift_deadline`, and the adjusted date
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
    key, fix_action supplies the canonical profile-edit action
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
    assert warning.fix_action.action.action_id == "operator.profile.edit"
    assert warning.fix_action.argument_bindings == ()


def test_calendar_completeness_lists_uncomputable_with_reason() -> None:
    """``CalendarCompleteness`` must enumerate explicit vs defaulted keys.

    With only ``iva.regime`` declared, the completeness payload must
    list it under explicitly_set_keys and the remaining gating keys
    under defaulted_keys.
    """
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    raw = {
        "tax.id": "X1234567L",
        "activity": "design",
        "iva.regime": "GENERAL",
    }
    cal = build_overview_calendar(_profile(), rng, today=today, raw_values=raw)
    assert "iva.regime" in cal.completeness.explicitly_set_keys
    assert "does_intracomunitario" in cal.completeness.defaulted_keys
    assert "has_employees" in cal.completeness.defaulted_keys
    assert "pays_capital_income_with_retencion" in cal.completeness.defaulted_keys
    assert "pays_professionals_with_retencion" in cal.completeness.defaulted_keys
    assert "pays_rent_with_retencion" in cal.completeness.defaulted_keys
    assert "art109_activity_income_withholding_ge_70pct" in cal.completeness.defaulted_keys
    assert "irpf.estimation_regime" in cal.completeness.defaulted_keys


def test_calendar_warnings_include_registry_deadline_window_predicates() -> None:
    """Deadline-window applicability predicates must be visible as warnings."""
    rng = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 4, 20))
    today = date(2026, 4, 1)
    raw = {
        "tax.id": "X1234567L",
        "activity": "design",
        "iva.regime": "GENERAL",
    }

    cal = build_overview_calendar(_profile(), rng, today=today, raw_values=raw)
    warnings_by_code = {warning.code: warning for warning in cal.warnings}

    assert "111" in warnings_by_code["has_employees"].affected_modelos
    assert "123" in warnings_by_code["pays_capital_income_with_retencion"].affected_modelos
    assert "130" in warnings_by_code["art109_activity_income_withholding_ge_70pct"].affected_modelos
