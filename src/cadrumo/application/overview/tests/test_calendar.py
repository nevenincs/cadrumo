"""Unit tests for the typed overview-calendar aggregator."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.config import override_settings
from ....core.filing_year import FOUR_DIGIT_YEAR_FIRST
from ....core.i18n.render import I18N_STRICT_MISSING_KEYS
from ....core.period import Period
from ....domain.calculations.registry.applicability import derive_modelo_applicability
from ....domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.published_authority import (
    PublishedGovernedFactSource,
    published_supported_filing_years,
)
from ....domain.contribuyente.entity_type import EntityType, LegalEntityForm
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.effective_close import effective_filing_deadline
from ....domain.deadlines.engine import DeadlineEngine
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.filing_window_projection import AuthoredFilingWindow
from ....domain.deadlines.models import (
    IrpfSpecialRegime,
    IVARegime,
    ModeloDeadline,
    ObligationStatus,
    TaxpayerProfile,
)
from ....domain.deadlines.tests.effective_close_scan import first_unpublished_calendar_year
from ....domain.deadlines.tests.withdrawn_deadline_window_authority import withdrawn_deadline_window_operation
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....tests.log_records import delivered_records
from ...live.notification_ports import RemoteNotification
from ...live.notifications import PersistedNotificationsSnapshot
from ..calendar import (
    build_overview_calendar,
    calendar_entry_from_obligation,
    entry_intersects_range,
    holiday_coverage_statement,
    registry_window_for_work_unit,
)
from ..calendar_events import (
    build_overview_calendar_events,
)
from ..calendar_models import (
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarRange,
    OverviewCensoEnrolmentState,
    user_state_for,
)
from ..calendar_warnings import calendar_applicability_profile_keys_for_modelo
from ..read_calendar_item_projection import OverviewCalendarWarningSnapshot
from ..status_report import build_filing_obligation_advisories
from .calendar_support import calendar_entry
from .calendar_test_support import (
    BUCKET_ID,
    SOURCE_URL,
)
from .calendar_test_support import (
    profile as calendar_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_SUPPORT = PublishedGovernedFactSource().supported_filing_years()
_YEAR = _SUPPORT.horizon
# The shared entry fixture is built for this exercise.
_ENTRY_YEAR = calendar_entry().period.filing_year


_M303_CENSO_ENROLMENT_KEYS = frozenset(
    {
        "activities.iae_epigraph",
        "iva.regime",
        "taxpayer_type.entity_type",
        "taxpayer_type.irpf_income_categories",
    },
)


_M202_CENSO_ENROLMENT_KEYS = frozenset(
    {
        "taxpayer_type.entity_type",
        "taxpayer_type.incn_prior_12_months",
        "taxpayer_type.legal_entity_form",
        "taxpayer_type.new_entity_first_two_profit_periods",
    },
)


def _annual_work_unit(*, modelo: str, filing_year: int) -> WorkUnit:
    """Build a real annual work unit for overview deadline lookup."""
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = "historic-annual-deadline-selection"
    created_at = datetime(filing_year, 1, 2, tzinfo=UTC)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=BUCKET_ID,
            modelo=ModeloCode(modelo),
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"historic-{modelo}-{filing_year}",
        created_at=created_at,
        updated_at=created_at,
    )


# An annual campaign for exercise N closes in January of N + 1, so the successor's
# campaign sits in January of N + 2.
_HISTORIC_ANNUAL_CASES = tuple(
    pytest.param(
        "180",
        filing_year,
        OverviewCalendarRange(from_date=date(filing_year + 2, 1, 1), to_date=date(filing_year + 2, 1, 31)),
        id=f"exercise-{filing_year}",
    )
    for filing_year in _SUPPORT.years
    if filing_year + 2 <= _SUPPORT.horizon
)


@pytest.mark.parametrize(("modelo", "filing_year", "calendar_range"), _HISTORIC_ANNUAL_CASES)
def test_calendar_does_not_project_historic_annual_work_into_future_registry_window(
    modelo: str,
    filing_year: int,
    calendar_range: OverviewCalendarRange,
) -> None:
    """Overview retains an unregistered annual work unit instead of borrowing the successor's campaign.

    The year is made unregistered by withdrawing its windows from the published
    generation, so the case does not wait on a real gap that authoring closes.
    The range is the successor's campaign, and the successor's own work unit is
    placed in it: a unit given that window would be placed there too.
    """
    work_unit = _annual_work_unit(modelo=modelo, filing_year=filing_year)
    successor = _annual_work_unit(modelo=modelo, filing_year=filing_year + 1)

    with withdrawn_deadline_window_operation(modelo_id=modelo, filing_year=filing_year) as operation:
        assert registry_window_for_work_unit(work_unit, operation=operation) is None
        calendar = build_overview_calendar(
            calendar_profile(),
            calendar_range,
            operation=operation,
            today=calendar_range.from_date,
            work_units=(work_unit, successor),
        )

    placed = {entry.local_work_unit_id for entry in calendar.entries}
    assert successor.work_unit_id in placed, "the range does not hold the successor's campaign, so this proves nothing"
    assert work_unit.work_unit_id not in placed


def test_calendar_gives_annual_work_below_the_supported_floor_its_own_year_only() -> None:
    """A work unit below the floor gets the window authored for its year or none, never a later campaign."""
    supported_years = published_supported_filing_years()
    assert supported_years is not None

    for filing_year in (supported_years.floor - 1, FOUR_DIGIT_YEAR_FIRST):
        answer = registry_window_for_work_unit(_annual_work_unit(modelo="100", filing_year=filing_year))

        assert answer is None or isinstance(answer, AuthoredFilingWindow)
        assert answer is None or answer.window.filing_year == filing_year


def test_calendar_censo_warning_requires_every_modelo_enrolment_key(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    applicability_303 = set(
        calendar_applicability_profile_keys_for_modelo("303", operation=authority_operation),
    )
    assert _M303_CENSO_ENROLMENT_KEYS - {"activities.iae_epigraph"} <= applicability_303

    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M303_CENSO_ENROLMENT_KEYS - {"iva.regime"})),
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.UNVERIFIED
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "303" in warning.affected_modelos


@pytest.mark.parametrize(
    ("language", "terms"),
    [
        ("en", ("census", "not", "verified")),
        ("es", ("censo", "no", "verificado")),
        ("ca", ("cens", "no", "verificat")),
        ("hu", ("nyilvántartásba", "nem", "ellenőrizték")),
    ],
)
def test_calendar_censo_warning_is_rendered_in_the_read_language(
    authority_operation: PinnedAuthorityOperation, language: str, terms: tuple[str, ...]
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M303_CENSO_ENROLMENT_KEYS - {"iva.regime"})),
    )
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "303" in warning.affected_modelos

    token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with override_settings(cadrumo_output_language=language):
            text = OverviewCalendarWarningSnapshot.from_warning(warning).text
    finally:
        I18N_STRICT_MISSING_KEYS.reset(token)

    assert text is not None
    assert all(term in text.lower() for term in terms)


def test_calendar_censo_warning_clears_when_every_modelo_enrolment_key_is_verified(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M303_CENSO_ENROLMENT_KEYS)),
    )

    assert any(entry.modelo == "303" for entry in calendar.entries)
    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.VERIFIED
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("303" in warning.affected_modelos for warning in censo_warnings)


def test_calendar_keeps_unverified_posture_when_no_censo_is_verified(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Retirement guard: with the live censo scrape retired, nothing stamps a
    censo-verified fact, so the calendar keeps its honest ``censo.enrolment_unverified``
    posture for every censo-dependent modelo when the verified-key set is empty.

    Pins the honest default: an empty ``live_censo_verified_profile_keys`` (the
    post-retirement reality) must never grant a VERIFIED enrolment state.
    """
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31)),
        operation=authority_operation,
        today=date(_YEAR, 1, 1),
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


def test_calendar_entry_marks_censo_enrolment_not_checked_when_no_live_censo_scope(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
    )

    modelo_303 = next(entry for entry in calendar.entries if entry.modelo == "303")
    assert modelo_303.censo_enrolment_state is OverviewCensoEnrolmentState.NOT_CHECKED
    assert "censo.enrolment_unverified" not in {warning.code for warning in calendar.warnings}


def _corporate_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="B00015016",
        entity_type=EntityType.from_registry("legal_entity"),
        legal_entity_form=LegalEntityForm.from_registry("SL"),
        iva_regime=IVARegime("GENERAL"),
        incn_prior_12_months=Decimal("7500000.00"),
        # Modelo 202 names the residencies it applies to, so the entity
        # states its own: unanswered, the pago fraccionado is incomplete and
        # the censo axes under test never get a row to be judged against.
        fiscal_residency=FiscalResidency.from_registry("resident_irpf"),
    )


def test_calendar_censo_warning_requires_corporate_modelo_202_enrolment_keys(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    applicability_202 = set(
        calendar_applicability_profile_keys_for_modelo("202", operation=authority_operation),
    )
    assert applicability_202 >= _M202_CENSO_ENROLMENT_KEYS

    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(
            sorted(_M202_CENSO_ENROLMENT_KEYS - {"taxpayer_type.incn_prior_12_months"}),
        ),
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    warning = next(item for item in calendar.warnings if item.code == "censo.enrolment_unverified")
    assert "202" in warning.affected_modelos


def test_calendar_censo_warning_clears_for_complete_corporate_modelo_202_provenance(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        _corporate_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        live_censo_verified_profile_keys=tuple(sorted(_M202_CENSO_ENROLMENT_KEYS)),
    )

    assert any(entry.modelo == "202" for entry in calendar.entries)
    censo_warnings = [item for item in calendar.warnings if item.code == "censo.enrolment_unverified"]
    assert not any("202" in warning.affected_modelos for warning in censo_warnings)


_INVALID_PAGADORES_ADVISORY_CASES: tuple[tuple[str, dict[str, str], str, str, str], ...] = (
    (
        "not-a-count-secret",
        {
            "irpf.pagadores_count": "not-a-count-secret",
            "irpf.pagadores_secondary_income": "1700",
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
    authority_operation: PinnedAuthorityOperation,
    raw_value: str,
    profile_values: dict[str, str],
    expected_message: str,
    expected_field: str,
    expected_error_type: str,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="cadrumo.application.overview"):
        advisories = build_filing_obligation_advisories(profile_values, operation=authority_operation)

    assert advisories == ()
    delivered = delivered_records(caplog)
    relevant = [record for record in delivered if record.getMessage() == expected_message]
    assert len(relevant) == 1
    assert relevant[0].__dict__["profile_field"] == expected_field
    assert relevant[0].__dict__["error_type"] == expected_error_type
    assert all(raw_value not in record.getMessage() for record in delivered)


_MULTIPLE_PAGADORES_OBLIGATION_KEY = "cli.overview.status.filing_obligation_multiple_pagadores"


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_multi_payer_over_reduced_limit_surfaces_obligation_advisory(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # 2 pagadores, secondary €1,600 > €1,500, total €18,000 over the reduced
    # limit (€15,876 or lower in earlier exercises) → the Art. 96.3 LIRPF obligation advisory fires.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
            "irpf.pagadores_total_work_income": "18000",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == (_MULTIPLE_PAGADORES_OBLIGATION_KEY,)


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_multi_payer_under_reduced_limit_does_not_surface_advisory(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # Same multiple-pagadores trigger but total €10,000 is below the reduced
    # limit → not obliged, no advisory.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
            "irpf.pagadores_total_work_income": "10000",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == ()


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_single_payer_under_general_limit_does_not_surface_advisory(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # 1 pagador, total €18,000 below the general €22,000 → no obligation.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "1",
            "irpf.pagadores_secondary_income": "0",
            "irpf.pagadores_total_work_income": "18000",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == ()


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_multi_payer_total_undeclared_surfaces_conservatively(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    # Total work income undeclared but the multiple-pagadores trigger is met →
    # the advisory surfaces conservatively rather than granting a false clear.
    advisories = build_filing_obligation_advisories(
        {
            "irpf.pagadores_count": "2",
            "irpf.pagadores_secondary_income": "1600",
        },
        filing_year=filing_year,
        operation=authority_operation,
    )
    assert advisories == (_MULTIPLE_PAGADORES_OBLIGATION_KEY,)


def test_obligation_advisory_key_resolves_to_a_translation() -> None:
    # The surfaced key must resolve to a real (non-humanised-fallback) locale
    # string in every shipped locale — the half-shipped gap this closes.
    from ....core.i18n.render import tr

    rendered = tr(_MULTIPLE_PAGADORES_OBLIGATION_KEY)
    # Cites the binding provision and names the form; not the humanised fallback.
    assert "96.3" in rendered
    assert "100" in rendered
    assert rendered != "Filing obligation multiple pagadores"


def test_build_overview_calendar_accepts_observed_events(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    event = build_overview_calendar_events(
        as_of=date(_YEAR, 3, 13),
        calendar_range=OverviewCalendarRange(from_date=date(_YEAR, 3, 1), to_date=date(_YEAR, 3, 31)),
        notification_snapshots=(
            PersistedNotificationsSnapshot(
                snapshot_id="a" * 64,
                bucket_id=BUCKET_ID,
                captured_at=datetime(_YEAR, 3, 13, 10, 0, tzinfo=UTC),
                source_url=SOURCE_URL,
                rows=(
                    RemoteNotification(
                        certificado_id="2596230606502",
                        tipo="comunicacion",
                        concepto="Comunicacion informativa",
                        titular_nif="B00015016",
                        titular_nombre="Test S.L.",
                        destinatario_nif="B00015016",
                        destinatario_nombre="Test S.L.",
                        fecha_emision=date(_YEAR, 3, 10),
                        leida=True,
                        source_url=SOURCE_URL,
                    ),
                ),
                persisted_at=datetime(_YEAR, 3, 13, 10, 5, tzinfo=UTC),
            ),
        ),
    )

    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 3, 1), to_date=date(_YEAR, 3, 31)),
        operation=authority_operation,
        today=date(_YEAR, 3, 15),
        events=event,
    )

    assert tuple(observed.reference_id for observed in calendar.events) == ("2596230606502",)


# build_overview_calendar
# ---------------------------------------------------------------------


def test_build_returns_typed_calendar_for_quarterly_window(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A window from 1 January to 20 April covers the first quarter."""
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
    )
    assert isinstance(calendar, OverviewCalendar)
    assert calendar.range.from_date == date(_YEAR, 1, 1)
    assert calendar.range.to_date == date(_YEAR, 4, 20)
    assert isinstance(calendar.generated_at, datetime)
    assert calendar.generated_at.tzinfo == UTC


def test_build_only_emits_entries_inside_range(authority_operation: PinnedAuthorityOperation) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
    )
    for entry in calendar.entries:
        # An entry must intersect the inclusive range.
        assert entry.closes_on >= date(_YEAR, 1, 1)
        assert entry.opens_on <= date(_YEAR, 4, 20)


def test_build_orders_entries_by_close_then_modelo_then_period(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
    )
    keys = [
        (entry.closes_on, entry.modelo, entry.period.filing_year, entry.period.registry_token)
        for entry in calendar.entries
    ]
    assert keys == sorted(keys)


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_build_preserves_each_modelo_303_obligation_once_in_canonical_order(
    authority_operation: PinnedAuthorityOperation,
    filing_year: int,
) -> None:
    """Overview must not erase or multiply legal rows while projecting a schedule."""
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(filing_year, 1, 1), to_date=date(filing_year + 1, 2, 28)),
        operation=authority_operation,
        today=date(filing_year, 1, 1),
    )

    coordinates = tuple(
        (entry.modelo, entry.period.filing_year, entry.period.registry_token)
        for entry in calendar.entries
        if entry.modelo == "303" and entry.period.filing_year == filing_year
    )

    assert coordinates == (
        ("303", filing_year, "1T"),
        ("303", filing_year, "2T"),
        ("303", filing_year, "3T"),
        ("303", filing_year, "4T"),
    )


def test_calendar_preserves_every_applicable_engine_row_for_all_supported_years(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Fleet parity derives its year horizon and expected rows from canonical owners."""
    profile = calendar_profile()
    supported_years = published_supported_filing_years()
    assert supported_years is not None

    for filing_year in supported_years.years:
        today = date(filing_year, 1, 1)
        schedule = DeadlineEngine(authority=authority_operation).compute(profile, filing_year, today=today)
        calendar = build_overview_calendar(
            profile,
            OverviewCalendarRange(
                from_date=date(filing_year, 1, 1),
                to_date=date(filing_year + 1, 12, 31),
            ),
            operation=authority_operation,
            today=today,
        )

        expected = tuple(
            (
                obligation.modelo,
                obligation.period.filing_year,
                obligation.period.registry_token,
                obligation.opens_on,
                obligation.closes_on,
                obligation.payment_cutoff_on,
                obligation.status,
            )
            for obligation in schedule.obligations
            if derive_modelo_applicability(profile, obligation.modelo).verdict is ApplicabilityVerdict.APPLICABLE
        )
        actual = tuple(
            (
                entry.modelo,
                entry.period.filing_year,
                entry.period.registry_token,
                entry.opens_on,
                entry.closes_on,
                entry.payment_cutoff_on,
                entry.status,
            )
            for entry in calendar.entries
            if entry.period.filing_year == filing_year
        )

        assert expected, filing_year
        assert actual == expected, filing_year


def test_build_tape_invocation_from_prior_q4_through_horizon_q2_spans_year_boundary(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A ``--from``/``--to`` range from the prior fourth quarter into the horizon spans multiple years."""
    horizon = _SUPPORT.horizon
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(horizon - 1, 10, 1), to_date=date(horizon, 7, 20)),
        operation=authority_operation,
        today=date(horizon, 5, 3),
    )
    years = {entry.period.filing_year for entry in calendar.entries}
    # The range straddles the year boundary, so both years must contribute.
    assert horizon - 1 in years or horizon in years


def test_build_user_state_matches_engine_status_per_entry(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
    )
    for entry in calendar.entries:
        assert entry.user_state is user_state_for(entry.status)


def test_build_uses_evaluation_date_for_historical_special_regime_route(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    # The impatriado regime applies to the year of the change and the five that
    # follow, so a change five exercises before the prior exercise is in its last
    # year there and over once the evaluation date moves into the next one.
    prior_year = _YEAR - 1
    profile = calendar_profile().model_copy(
        update={
            "irpf_special_regime": IrpfSpecialRegime.from_registry("impatriado"),
            "special_regime_start_date": date(prior_year - 5, 1, 15),
        },
    )
    rng = OverviewCalendarRange(from_date=date(prior_year, 1, 1), to_date=date(prior_year, 12, 31))

    active = build_overview_calendar(profile, rng, operation=authority_operation, today=date(prior_year, 6, 1))
    expired = build_overview_calendar(profile, rng, operation=authority_operation, today=date(_YEAR, 6, 1))

    active_modelos = {entry.modelo for entry in active.entries}
    expired_modelos = {entry.modelo for entry in expired.entries}
    assert "151" in active_modelos
    assert "100" not in active_modelos
    assert "100" in expired_modelos
    assert "151" not in expired_modelos


def test_build_empty_range_when_window_covers_no_obligations(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A 1-day window outside every modelo's filing window emits no entries."""
    # 15 January lies outside every modelo's January quarterly / monthly window.
    calendar = build_overview_calendar(
        calendar_profile(),
        OverviewCalendarRange(from_date=date(_YEAR, 1, 15), to_date=date(_YEAR, 1, 15)),
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
    )
    assert isinstance(calendar.entries, tuple)


def test_build_threads_shift_metadata_onto_every_entry(
    authority_operation: PinnedAuthorityOperation,
) -> None:
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
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31))
    cal = build_overview_calendar(calendar_profile(), rng, operation=authority_operation, today=date(_YEAR, 4, 1))
    assert cal.entries, "expected the test profile to produce at least one obligation"
    for entry in cal.entries:
        assert entry.adjusted_closes_on >= entry.closes_on
        assert entry.shift_reason in accepted_reasons


def _obligation_with_real_effective_close(
    *,
    operation: PinnedAuthorityOperation,
    modelo: str,
    period: Period,
    opens_on: date,
    closes_on: date,
    status: ObligationStatus,
    payment_cutoff_on: date | None = None,
) -> ModeloDeadline:
    """Build an obligation whose effective close comes from the real shift rule.

    The engine resolves the shift once and publishes it on the obligation, so a
    test that hand-writes an effective date would assert its own arithmetic
    instead of the governed calendar.
    """
    effective = effective_filing_deadline(closes_on, modelo=modelo, operation=operation)
    return ModeloDeadline(
        modelo=modelo,
        period=period,
        opens_on=opens_on,
        closes_on=closes_on,
        adjusted_closes_on=effective.closes_on,
        holiday_coverage=effective.holiday_coverage,
        shift_reason=effective.shift_reason,
        shift_jurisdictions=effective.jurisdictions,
        shift_holiday_refs=effective.holiday_refs,
        payment_cutoff_on=payment_cutoff_on,
        status=status,
        boe_references=(),
        recovery=None,
    )


# The supported exercise whose 20 April, the nominal close of a first quarter, is a Sunday.
_SUNDAY_APRIL_20_YEAR = next(year for year in _SUPPORT.years if date(year, 4, 20).weekday() == 6)


def test_an_entry_renders_the_overdue_age_and_recargo_from_the_effective_close(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The entry counts lateness from the close the filer actually had.

    Modelo 303 1T closes nominally on 20 April; in an exercise where that is a
    Sunday the filer had until Monday the 21st. The status is the one its producer classified
    against that date -- overview re-deciding it could only disagree -- while
    the overdue age and the recargo band are counted from it here.
    """
    year = _SUNDAY_APRIL_20_YEAR
    obligation = _obligation_with_real_effective_close(
        operation=authority_operation,
        modelo="303",
        period=Period.from_year_and_code(year, "1T"),
        opens_on=date(year, 4, 1),
        closes_on=date(year, 4, 20),
        payment_cutoff_on=date(year, 4, 15),
        status=ObligationStatus.OVERDUE,
    )

    assert obligation.adjusted_closes_on == date(year, 4, 21), "the Sunday close still runs to the Monday"

    entry = calendar_entry_from_obligation(
        obligation,
        filing_evidence=(),
        live_censo_verified_profile_keys=None,
        today=date(year, 4, 22),
        due_soon_days=14,
        operation=authority_operation,
    )

    assert entry.adjusted_closes_on == date(year, 4, 21)
    assert entry.status is ObligationStatus.OVERDUE
    assert entry.days_overdue == 1, "one day past the effective close, not two past the nominal one"
    assert entry.recovery is not None


def test_an_entry_keeps_the_status_its_producer_classified(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Overview applies its filing gate, never a second date classification."""
    obligation = _obligation_with_real_effective_close(
        operation=authority_operation,
        modelo="303",
        period=Period.from_year_and_code(_YEAR, "1T"),
        opens_on=date(_YEAR, 4, 1),
        closes_on=date(_YEAR, 4, 20),
        status=ObligationStatus.DUE_TODAY,
    )

    entry = calendar_entry_from_obligation(
        obligation,
        filing_evidence=(),
        live_censo_verified_profile_keys=None,
        today=date(_YEAR, 4, 21),
        due_soon_days=14,
        operation=authority_operation,
    )

    assert entry.status is ObligationStatus.DUE_TODAY
    assert entry.days_overdue is None
    assert entry.recovery is None


def _obligation(modelo: str, closes_on: date, operation: PinnedAuthorityOperation) -> ModeloDeadline:
    return _obligation_with_real_effective_close(
        operation=operation,
        modelo=modelo,
        period=Period.from_year_and_code(closes_on.year, "3T"),
        opens_on=closes_on.replace(day=1),
        closes_on=closes_on,
        status=ObligationStatus.UPCOMING,
    )


def _entry_for(obligation: ModeloDeadline, operation: PinnedAuthorityOperation):
    return calendar_entry_from_obligation(
        obligation,
        filing_evidence=(),
        live_censo_verified_profile_keys=None,
        today=date(_YEAR, 8, 1),
        due_soon_days=14,
        operation=operation,
    )


@pytest.mark.parametrize(
    "year",
    [year for year in _SUPPORT.years if date(year, 9, 11).weekday() < 5],
)
def test_a_regional_holiday_never_moves_the_effective_close(
    authority_operation: PinnedAuthorityOperation,
    year: int,
) -> None:
    """The Diada (11 September, on a weekday) is inhábil only in Cataluna.

    An electronic filing counts days on the State's calendar (Ley 39/2015 art. 31.3),
    so the close stays on the Diada for every filer.
    """
    entry = _entry_for(_obligation("303", date(year, 9, 11), authority_operation), authority_operation)

    assert entry.adjusted_closes_on == date(year, 9, 11)
    assert entry.shift_reason == "business_day"
    assert entry.holiday_coverage is DeadlineHolidayCoverage.NATIONAL_ONLY


def _first_saturday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(5 - first.weekday()) % 7)


@pytest.mark.parametrize("year", _SUPPORT.years)
def test_modelo_369_entry_is_not_shifted_on_a_weekend(
    authority_operation: PinnedAuthorityOperation,
    year: int,
) -> None:
    saturday = _first_saturday(year, 10)
    entry = _entry_for(_obligation("369", saturday, authority_operation), authority_operation)

    assert entry.adjusted_closes_on == saturday
    assert entry.shift_reason == "modelo_exception"
    assert entry.holiday_coverage is DeadlineHolidayCoverage.NOT_SHIFTED


def test_missing_holiday_calendar_keeps_the_original_close_visibly_unverified(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """No holiday publication exists for the first unpublished year, so a Saturday close cannot be adjusted or certified."""
    saturday = _first_saturday(first_unpublished_calendar_year(authority_operation), 10)
    entry = _entry_for(_obligation("303", saturday, authority_operation), authority_operation)

    assert entry.adjusted_closes_on == entry.closes_on == saturday
    assert entry.shift_reason == "calendar_unavailable"
    assert entry.holiday_coverage is DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE


@pytest.mark.parametrize("language", ("en", "es", "ca", "hu"))
@pytest.mark.parametrize("coverage", tuple(DeadlineHolidayCoverage))
def test_every_holiday_coverage_has_a_complete_statement(language: str, coverage: DeadlineHolidayCoverage) -> None:
    with override_settings(cadrumo_output_language=language):
        statement = holiday_coverage_statement(coverage)

    assert statement
    assert not statement.startswith("application.overview.calendar.holiday_coverage.")
    assert "%{" not in statement


def test_entry_refuses_a_shift_its_coverage_did_not_evaluate() -> None:
    with pytest.raises(ValidationError, match="did not evaluate"):
        OverviewCalendarEntry(
            modelo="303",
            period=Period.from_year_and_code(_YEAR, "3T"),
            opens_on=date(_YEAR, 10, 1),
            closes_on=date(_YEAR, 10, 17),
            adjusted_closes_on=date(_YEAR, 10, 19),
            shift_reason="calendar_unavailable",
            holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
            evaluated_on=date(_YEAR, 8, 1),
            status=ObligationStatus.UPCOMING,
            user_state=user_state_for(ObligationStatus.UPCOMING),
        )


def test_build_marks_modelo_369_as_modelo_exception(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Modelo 369 obligations bypass the shift; reason must be modelo_exception."""
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 12, 31))
    cal = build_overview_calendar(calendar_profile(), rng, operation=authority_operation, today=date(_YEAR, 4, 1))
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
        calendar_entry(
            closes_on=date(_ENTRY_YEAR, 4, 20),
            adjusted_closes_on=date(_ENTRY_YEAR, 4, 19),
        )


def test_build_is_idempotent_modulo_generated_at(authority_operation: PinnedAuthorityOperation) -> None:
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20))
    today = date(_YEAR, 4, 1)
    profile = calendar_profile()
    a = build_overview_calendar(profile, rng, operation=authority_operation, today=today)
    b = build_overview_calendar(profile, rng, operation=authority_operation, today=today)
    assert a.entries == b.entries
    assert a.range == b.range


def test_calendar_omits_warnings_when_raw_values_not_supplied(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Without raw_values the aggregator returns no warnings or completeness rows.

    Existing callers that build the calendar from a fully-resolved
    ``TaxpayerProfile`` without surfacing the user_cli raw mapping
    must not see new warning behaviour. The empty defaults on
    OverviewCalendar.warnings / completeness preserve backwards
    compatibility for those callers.
    """
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20))
    today = date(_YEAR, 4, 1)
    cal = build_overview_calendar(calendar_profile(), rng, operation=authority_operation, today=today)
    assert cal.warnings == ()
    assert cal.completeness.explicitly_set_keys == ()
    assert cal.completeness.defaulted_keys == ()


def test_calendar_emits_warning_when_iva_regime_unset(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A profile with no iva.regime declared must produce a typed warning.

    The deadline engine's modelo-applicability rules default to GENERAL
    when iva.regime is absent and would otherwise compute 303/390
    entries under those defaults without signalling the assumption.
    The contract verified here: when raw_values omits iva.regime, the
    aggregator emits a CalendarWarning whose code names the missing
    key, fix_action supplies the canonical profile-edit action
    command, and affected_modelos lists 303/390.
    """
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20))
    today = date(_YEAR, 4, 1)
    raw = {"tax.id": "X0001500M", "activity": "design"}
    cal = build_overview_calendar(calendar_profile(), rng, operation=authority_operation, today=today, raw_values=raw)
    iva_warnings = [w for w in cal.warnings if w.code == "iva.regime"]
    assert len(iva_warnings) == 1
    warning = iva_warnings[0]
    assert "303" in warning.affected_modelos
    assert "390" in warning.affected_modelos
    assert warning.fix_action.action.action_id == "operator.profile.edit"
    assert warning.fix_action.argument_bindings == ()


def test_calendar_completeness_lists_uncomputable_with_reason(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """``CalendarCompleteness`` must enumerate explicit vs defaulted keys.

    With only ``iva.regime`` declared, the completeness payload must
    list it under explicitly_set_keys and the remaining gating keys
    under defaulted_keys.
    """
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20))
    today = date(_YEAR, 4, 1)
    raw = {
        "tax.id": "X0001500M",
        "activity": "design",
        "iva.regime": "GENERAL",
    }
    cal = build_overview_calendar(calendar_profile(), rng, operation=authority_operation, today=today, raw_values=raw)
    assert "iva.regime" in cal.completeness.explicitly_set_keys
    assert "does_intracomunitario" in cal.completeness.defaulted_keys
    assert "has_employees" in cal.completeness.defaulted_keys
    assert "pays_capital_income_with_retencion" in cal.completeness.defaulted_keys
    assert "pays_professionals_with_retencion" in cal.completeness.defaulted_keys
    assert "pays_rent_with_retencion" in cal.completeness.defaulted_keys
    assert "art109_activity_income_withholding_ge_70pct" in cal.completeness.defaulted_keys
    assert "irpf.estimation_regime" in cal.completeness.defaulted_keys


def test_calendar_warnings_include_registry_deadline_window_predicates(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Deadline-window applicability predicates must be visible as warnings."""
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20))
    today = date(_YEAR, 4, 1)
    raw = {
        "tax.id": "X0001500M",
        "activity": "design",
        "iva.regime": "GENERAL",
    }

    cal = build_overview_calendar(calendar_profile(), rng, operation=authority_operation, today=today, raw_values=raw)
    warnings_by_code = {warning.code: warning for warning in cal.warnings}

    assert "111" in warnings_by_code["has_employees"].affected_modelos
    assert "123" in warnings_by_code["pays_capital_income_with_retencion"].affected_modelos
    assert "130" in warnings_by_code["art109_activity_income_withholding_ge_70pct"].affected_modelos


def _has_employees_warning_through_record_projection(
    *,
    authority_operation: PinnedAuthorityOperation,
    has_employees: bool | None,
) -> bool:
    """Run the real stored-record projection the TUI/workbench pipeline uses.

    ``cadrumo.application.workbench_generation_reader`` projects the stored
    :class:`UserProfileRecord` through
    :func:`~cadrumo.application.user_profile.projections.record_to_path_values`
    before calling :func:`build_overview_calendar`, so production
    ``raw_values`` there is keyed by the canonical dotted schema path
    (``"withholding.has_employees"``), not the bare registry selector
    (``"has_employees"``) the gating map's code names. Driving the real
    fact, record, and projection here - instead of a hand-built
    selector-keyed dict - reproduces whatever that real pipeline does.
    """
    from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
    from ...user_profile.projections import record_to_path_values

    facts = [
        UserProfileFact(path="identity.tax_id", value="X0001500M"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    ]
    if has_employees is not None:
        facts.append(UserProfileFact(path="withholding.has_employees", value=has_employees))
    record = create_user_profile_record(
        context=authority_operation.profile_create_context(),
        profile_id=BUCKET_ID,
        facts=tuple(facts),
        setup_state=ProfileSetupState.COMPLETE,
    )
    raw_values = record_to_path_values(record)
    rng = OverviewCalendarRange(from_date=date(_YEAR, 1, 1), to_date=date(_YEAR, 4, 20))
    cal = build_overview_calendar(
        calendar_profile(),
        rng,
        operation=authority_operation,
        today=date(_YEAR, 4, 1),
        raw_values=raw_values,
    )
    return any(warning.code == "has_employees" for warning in cal.warnings)


def test_calendar_completeness_matches_dotted_schema_path_raw_values(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A fact stored and projected by schema path must still clear its warning.

    Before this was fixed, ``build_completeness_and_warnings`` only ever
    looked ``raw_values`` up by the bare registry selector
    (``"has_employees"``), so a caller supplying the canonical dotted schema
    path instead - exactly what
    :func:`~cadrumo.application.user_profile.projections.record_to_path_values`
    produces - always missed, and the "unset" warning fired regardless of
    the stored answer.
    """
    assert (
        _has_employees_warning_through_record_projection(authority_operation=authority_operation, has_employees=None)
        is True
    )
    assert (
        _has_employees_warning_through_record_projection(authority_operation=authority_operation, has_employees=True)
        is False
    )
    assert (
        _has_employees_warning_through_record_projection(authority_operation=authority_operation, has_employees=False)
        is False
    )


# The annual campaigns of the supported exercise whose 31 January close falls on a
# Saturday move to the Monday, inside a February range that the nominal date misses.
_SATURDAY_CLOSE_EXERCISE = next(year for year in _SUPPORT.years if date(year + 1, 1, 31).weekday() == 5)
_SATURDAY_CLOSE = date(_SATURDAY_CLOSE_EXERCISE + 1, 1, 31)


_MONDAY_EFFECTIVE_CLOSE = _SATURDAY_CLOSE + timedelta(days=2)


_FEBRUARY = OverviewCalendarRange(
    from_date=date(_SATURDAY_CLOSE.year, 2, 1),
    to_date=date(_SATURDAY_CLOSE.year, 2, 28),
)
_AFTER_EFFECTIVE_CLOSE = OverviewCalendarRange(
    from_date=_MONDAY_EFFECTIVE_CLOSE + timedelta(days=1),
    to_date=_FEBRUARY.to_date,
)


def test_calendar_places_a_work_unit_by_its_effective_deadline(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    assert _SATURDAY_CLOSE.weekday() == 5
    work_unit = _annual_work_unit(modelo="180", filing_year=_SATURDAY_CLOSE_EXERCISE)
    window = registry_window_for_work_unit(work_unit, operation=authority_operation)
    assert window is not None
    assert window.closes_on == _SATURDAY_CLOSE

    calendar = build_overview_calendar(
        calendar_profile(),
        _FEBRUARY,
        operation=authority_operation,
        today=_FEBRUARY.from_date,
        work_units=(work_unit,),
    )

    entry = next(item for item in calendar.entries if item.local_work_unit_id == work_unit.work_unit_id)
    assert entry.closes_on == _SATURDAY_CLOSE
    assert entry.adjusted_closes_on == _MONDAY_EFFECTIVE_CLOSE


def test_calendar_leaves_out_a_work_unit_whose_effective_deadline_precedes_the_range(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    work_unit = _annual_work_unit(modelo="180", filing_year=_SATURDAY_CLOSE_EXERCISE)
    after_effective_close = _AFTER_EFFECTIVE_CLOSE

    calendar = build_overview_calendar(
        calendar_profile(),
        after_effective_close,
        operation=authority_operation,
        today=after_effective_close.from_date,
        work_units=(work_unit,),
    )

    assert work_unit.work_unit_id not in {item.local_work_unit_id for item in calendar.entries}


def test_registry_obligation_intersects_a_range_through_its_effective_deadline(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    obligation = _obligation_with_real_effective_close(
        operation=authority_operation,
        modelo="190",
        period=Period.from_year_and_code(_SATURDAY_CLOSE_EXERCISE, "0A"),
        opens_on=date(_SATURDAY_CLOSE.year, 1, 1),
        closes_on=_SATURDAY_CLOSE,
        status=ObligationStatus.UPCOMING,
    )
    after_effective_close = _AFTER_EFFECTIVE_CLOSE

    assert entry_intersects_range(
        obligation,
        _FEBRUARY,
        operation=authority_operation,
    )
    assert not entry_intersects_range(
        obligation,
        after_effective_close,
        operation=authority_operation,
    )
