"""Per-area AEAT sync staleness, judged through the real status reader.

Every horizon is an owner ruling, so the expected days are written here
independently of the constants under test: notifications 7, IVA wallet 30, and
census, filed declarations and identity checks 90. An area is possibly stale
once its last successful capture is STRICTLY older than its horizon, so each
boundary is exercised from both sides.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from ....core.period import Period
from ...calculations.ports import FiledDeclaracionObservationProtocol
from ...overview.calendar_models import OverviewAeatSubmissionState, OverviewCalendarFilingEvidence
from ...overview.evidence import (
    AeatCalendarEvidenceSources,
    CalendarEvidenceReadOutcome,
    LocalCalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from ...overview.home import HomeAvailability, HomeZoneState
from ...user_profile.censal_observation import CensalObservation, CensalObservationAddress, CensalObservationIdentity
from ..workspace import AeatSyncAreaState, AeatSyncStatusArea, AeatSyncStatusV1
from ..workspace_reader import (
    AeatSyncAreaAttempt,
    AeatSyncNotificationsCapture,
    AeatSyncStatusSources,
    read_aeat_sync_status,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
_SUBJECT = "X1234567L"
_UNREADABLE = "aeat_sync.status.store_unreadable"
_YEARS = (2025, 2026)

_HORIZON_DAYS = {
    AeatSyncStatusArea.NOTIFICATIONS: 7,
    AeatSyncStatusArea.IVA_WALLET: 30,
    AeatSyncStatusArea.CENSUS: 90,
    AeatSyncStatusArea.FILED_DECLARATIONS: 90,
    AeatSyncStatusArea.IDENTITY_CHECKS: 90,
}


def _census(captured_at: datetime) -> CensalObservation:
    return CensalObservation(
        identity=CensalObservationIdentity(nif=_SUBJECT),
        domicilio_fiscal=CensalObservationAddress(codigo_postal="28001"),
        domicilio_notificacion=CensalObservationAddress(),
        captured_at=captured_at,
        source_url="https://sede.agenciatributaria.gob.es/censo",
    )


def _filed_evidence(
    captured_at: datetime | None,
    *,
    availability: HomeAvailability = HomeAvailability.AVAILABLE,
    observations: tuple[FiledDeclaracionObservationProtocol, ...] = (),
):
    """Join stored register captures taken at ``captured_at`` through the calendar's own provider."""
    observable = availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}
    return build_calendar_evidence_projection(
        local=CalendarEvidenceReadOutcome(
            state=HomeZoneState(availability=HomeAvailability.AVAILABLE),
            value=LocalCalendarEvidenceSources(),
        ),
        aeat=CalendarEvidenceReadOutcome(
            state=HomeZoneState(
                availability=availability,
                observed_at=captured_at if observable else None,
                reason_code=None if availability is HomeAvailability.AVAILABLE else _UNREADABLE,
            ),
            value=AeatCalendarEvidenceSources(filed_declaration_observations=observations) if observable else None,
        ),
        expected_tax_id=_SUBJECT,
    )


def _sources_captured_at(area: AeatSyncStatusArea, captured_at: datetime) -> AeatSyncStatusSources:
    """Sources in which only ``area`` holds a capture, taken at ``captured_at``."""
    match area:
        case AeatSyncStatusArea.CENSUS:
            return AeatSyncStatusSources(census_observation=_census(captured_at))
        case AeatSyncStatusArea.FILED_DECLARATIONS:
            return AeatSyncStatusSources(filed_evidence=_filed_evidence(captured_at))
        case AeatSyncStatusArea.NOTIFICATIONS:
            return AeatSyncStatusSources(
                notifications=AeatSyncNotificationsCapture(captured_at=captured_at, unread_count=0)
            )
        case AeatSyncStatusArea.IVA_WALLET:
            return AeatSyncStatusSources(iva_wallet_captured_at=captured_at)
        case AeatSyncStatusArea.IDENTITY_CHECKS:
            return AeatSyncStatusSources(identity_checked_at=captured_at)
        case AeatSyncStatusArea.BORRADOR_100:
            return AeatSyncStatusSources(borrador_imported_at=captured_at)


def _status(sources: AeatSyncStatusSources) -> AeatSyncStatusV1:
    return read_aeat_sync_status(
        observed_at=_NOW,
        sources=sources,
        filed_declaration_years=_YEARS,
        iva_wallet_years=_YEARS,
    )


def _area(status: AeatSyncStatusV1, area: AeatSyncStatusArea):
    return next(item for item in status.areas if item.area is area)


@pytest.mark.parametrize("area", tuple(_HORIZON_DAYS))
@pytest.mark.parametrize(
    ("age_offset", "state"),
    (
        (timedelta(days=-1), AeatSyncAreaState.CURRENT),
        (timedelta(0), AeatSyncAreaState.CURRENT),
        (timedelta(seconds=-1), AeatSyncAreaState.CURRENT),
        (timedelta(seconds=1), AeatSyncAreaState.POSSIBLY_STALE),
        (timedelta(days=1), AeatSyncAreaState.POSSIBLY_STALE),
    ),
    ids=("a day inside", "exactly at the horizon", "a second inside", "a second past", "a day past"),
)
def test_each_area_turns_possibly_stale_only_strictly_after_its_horizon(
    area: AeatSyncStatusArea, age_offset: timedelta, state: AeatSyncAreaState
) -> None:
    horizon = timedelta(days=_HORIZON_DAYS[area])
    captured_at = _NOW - horizon - age_offset

    row = _area(_status(_sources_captured_at(area, captured_at)), area)

    assert row.state is state
    assert row.last_brought_at == captured_at
    assert row.stale_after_days == _HORIZON_DAYS[area]


@pytest.mark.parametrize("area", tuple(AeatSyncStatusArea))
def test_a_capture_made_just_now_is_current_and_one_from_the_future_is_not_stale(area: AeatSyncStatusArea) -> None:
    for captured_at in (_NOW, _NOW + timedelta(hours=1)):
        row = _area(_status(_sources_captured_at(area, captured_at)), area)

        assert row.state is AeatSyncAreaState.CURRENT
        assert row.last_brought_at == captured_at


def test_borrador_100_has_no_ruled_horizon_so_it_is_never_judged_stale() -> None:
    imported_at = _NOW - timedelta(days=3650)

    row = _area(
        _status(_sources_captured_at(AeatSyncStatusArea.BORRADOR_100, imported_at)), AeatSyncStatusArea.BORRADOR_100
    )

    assert row.state is AeatSyncAreaState.CURRENT
    assert row.stale_after_days is None
    assert row.last_brought_at == imported_at


def test_horizons_differ_by_area_for_one_capture_age() -> None:
    """Twenty days is past the notifications horizon only, inside the IVA wallet's and the 90-day areas'."""
    captured_at = _NOW - timedelta(days=20)
    sources = AeatSyncStatusSources(
        census_observation=_census(captured_at),
        identity_checked_at=captured_at,
        notifications=AeatSyncNotificationsCapture(captured_at=captured_at, unread_count=0),
        iva_wallet_captured_at=captured_at,
        filed_evidence=_filed_evidence(captured_at),
    )

    states = {item.area: item.state for item in _status(sources).areas}

    assert states == {
        AeatSyncStatusArea.CENSUS: AeatSyncAreaState.CURRENT,
        AeatSyncStatusArea.IDENTITY_CHECKS: AeatSyncAreaState.CURRENT,
        AeatSyncStatusArea.NOTIFICATIONS: AeatSyncAreaState.POSSIBLY_STALE,
        AeatSyncStatusArea.IVA_WALLET: AeatSyncAreaState.CURRENT,
        AeatSyncStatusArea.FILED_DECLARATIONS: AeatSyncAreaState.CURRENT,
        AeatSyncStatusArea.BORRADOR_100: AeatSyncAreaState.NEVER_BROUGHT,
    }


def test_a_fresh_profile_has_every_area_never_brought_in_run_order() -> None:
    status = _status(AeatSyncStatusSources())

    assert [item.area for item in status.areas] == [
        AeatSyncStatusArea.CENSUS,
        AeatSyncStatusArea.IDENTITY_CHECKS,
        AeatSyncStatusArea.NOTIFICATIONS,
        AeatSyncStatusArea.IVA_WALLET,
        AeatSyncStatusArea.FILED_DECLARATIONS,
        AeatSyncStatusArea.BORRADOR_100,
    ]
    assert {item.state for item in status.areas} == {AeatSyncAreaState.NEVER_BROUGHT}
    assert all(item.last_brought_at is None for item in status.areas)
    assert (status.filed_declaration_years, status.iva_wallet_years) == (_YEARS, _YEARS)


def test_an_unreadable_store_is_unavailable_even_when_a_capture_time_is_known() -> None:
    """A time the store cannot confirm is not proof, and unavailable is not never brought."""
    sources = AeatSyncStatusSources(
        iva_wallet_captured_at=_NOW,
        unreadable={AeatSyncStatusArea.IVA_WALLET: _UNREADABLE, AeatSyncStatusArea.NOTIFICATIONS: _UNREADABLE},
    )

    status = _status(sources)

    wallet = _area(status, AeatSyncStatusArea.IVA_WALLET)
    assert (wallet.state, wallet.refusal, wallet.last_brought_at) == (AeatSyncAreaState.UNAVAILABLE, _UNREADABLE, None)
    notifications = _area(status, AeatSyncStatusArea.NOTIFICATIONS)
    assert notifications.state is AeatSyncAreaState.UNAVAILABLE
    assert _area(status, AeatSyncStatusArea.CENSUS).state is AeatSyncAreaState.NEVER_BROUGHT


@pytest.mark.parametrize(
    ("availability", "state"),
    (
        (HomeAvailability.NEVER_CAPTURED, AeatSyncAreaState.NEVER_BROUGHT),
        (HomeAvailability.UNAVAILABLE, AeatSyncAreaState.UNAVAILABLE),
        (HomeAvailability.STALE, AeatSyncAreaState.CURRENT),
    ),
)
def test_filed_declarations_keep_never_captured_unreadable_and_captured_apart(
    availability: HomeAvailability, state: AeatSyncAreaState
) -> None:
    captured_at = _NOW - timedelta(days=1)

    row = _area(
        _status(AeatSyncStatusSources(filed_evidence=_filed_evidence(captured_at, availability=availability))),
        AeatSyncStatusArea.FILED_DECLARATIONS,
    )

    assert row.state is state
    assert (row.last_brought_at, row.refusal) == (
        (captured_at, None) if state is AeatSyncAreaState.CURRENT else (None, row.refusal)
    )
    assert (row.filed_periods is not None) is (state is AeatSyncAreaState.CURRENT)
    assert (row.refusal is not None) is (state is AeatSyncAreaState.UNAVAILABLE)


def test_filed_periods_partition_matched_aeat_only_local_only_and_differing() -> None:
    from ...overview.tests.calendar_test_support import filed_declaration_observation, modelo_record

    first = filed_declaration_observation(artefacts=())
    second = replace(
        filed_declaration_observation(artefacts=(), expediente_id="22222222222222222222"),
        _period=Period.from_year_and_code(2025, "2T"),
    )
    captured_at = _NOW - timedelta(days=2)
    joined = _filed_evidence(captured_at, observations=(first, second))
    contested = OverviewCalendarFilingEvidence(
        modelo="130",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "1T"),
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        aeat_evidence_conflict_reference_ids=("conflicting-register-row",),
    )
    filings = (
        modelo_record(),
        modelo_record(period=Period.from_year_and_code(2025, "3T")),
        modelo_record(modelo="130"),
    )

    row = _area(
        _status(
            AeatSyncStatusSources(
                filings=filings,
                filed_evidence=replace(joined, evidence=(*joined.evidence, contested)),
            )
        ),
        AeatSyncStatusArea.FILED_DECLARATIONS,
    )

    assert row.filed_periods is not None
    assert (
        row.filed_periods.matched,
        row.filed_periods.aeat_only,
        row.filed_periods.local_only,
        row.filed_periods.differing,
    ) == (1, 1, 1, 1)


def test_an_observed_empty_register_reports_every_local_filing_as_local_only() -> None:
    from ...overview.tests.calendar_test_support import modelo_record

    row = _area(
        _status(
            AeatSyncStatusSources(filings=(modelo_record(),), filed_evidence=_filed_evidence(_NOW - timedelta(days=1)))
        ),
        AeatSyncStatusArea.FILED_DECLARATIONS,
    )

    assert row.filed_periods is not None
    assert (row.filed_periods.matched, row.filed_periods.aeat_only, row.filed_periods.local_only) == (0, 0, 1)


def test_notifications_carry_their_unread_count_and_other_areas_carry_none() -> None:
    sources = AeatSyncStatusSources(
        notifications=AeatSyncNotificationsCapture(captured_at=_NOW - timedelta(days=1), unread_count=3),
    )

    status = _status(sources)

    assert _area(status, AeatSyncStatusArea.NOTIFICATIONS).unread_notification_count == 3
    assert {
        item.unread_notification_count for item in status.areas if item.area is not AeatSyncStatusArea.NOTIFICATIONS
    } == {None}


def test_a_failed_attempt_without_any_capture_is_still_never_brought() -> None:
    attempted_at = _NOW - timedelta(hours=2)

    row = _area(
        _status(AeatSyncStatusSources(filed_attempt=AeatSyncAreaAttempt(attempted_at=attempted_at, succeeded=False))),
        AeatSyncStatusArea.FILED_DECLARATIONS,
    )

    assert row.state is AeatSyncAreaState.NEVER_BROUGHT
    assert (row.last_attempt_at, row.last_attempt_succeeded) == (attempted_at, False)
    assert row.last_brought_at is None


def test_the_status_round_trips_through_json_with_its_states_intact() -> None:
    status = _status(_sources_captured_at(AeatSyncStatusArea.NOTIFICATIONS, _NOW - timedelta(days=8)))

    restored = AeatSyncStatusV1.model_validate_json(status.model_dump_json())

    assert restored == status
    assert _area(restored, AeatSyncStatusArea.NOTIFICATIONS).state is AeatSyncAreaState.POSSIBLY_STALE
