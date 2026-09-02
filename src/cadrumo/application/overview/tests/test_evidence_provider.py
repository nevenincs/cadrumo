"""Contract tests for the frontend-neutral overview evidence provider."""

from __future__ import annotations

import builtins
import socket
from datetime import UTC, date, datetime

import pytest

from ....core.period import Period
from ..calendar_models import OverviewAeatSubmissionState, OverviewCalendarEvent, OverviewCalendarEventType
from ..evidence import (
    CalendarEvidenceReadOutcome,
    CalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from ..home import HomeAvailability, HomeZoneState
from .calendar_test_support import modelo_record

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_OBSERVED_AT = datetime(2026, 8, 31, 9, 15, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")


def _state(
    availability: HomeAvailability,
    *,
    observed_at: datetime | None = None,
) -> HomeZoneState:
    return HomeZoneState(
        availability=availability,
        observed_at=observed_at,
        reason_code=None if availability is HomeAvailability.AVAILABLE else f"evidence.{availability.value}",
    )


def _local(
    availability: HomeAvailability = HomeAvailability.AVAILABLE,
    *,
    records: tuple = (),
    observed_at: datetime | None = None,
) -> CalendarEvidenceReadOutcome:
    return CalendarEvidenceReadOutcome(
        state=_state(availability, observed_at=observed_at),
        value=(
            CalendarEvidenceSources(filing_records=records)
            if availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}
            else None
        ),
    )


def _aeat(
    availability: HomeAvailability = HomeAvailability.AVAILABLE,
    *,
    events: tuple[OverviewCalendarEvent, ...] = (),
    observed_at: datetime | None = None,
) -> CalendarEvidenceReadOutcome:
    return CalendarEvidenceReadOutcome(
        state=_state(availability, observed_at=observed_at),
        value=(
            CalendarEvidenceSources(observed_events=events)
            if availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}
            else None
        ),
    )


def _observed_event(*, modelo: str = "303", period: Period = _PERIOD) -> OverviewCalendarEvent:
    return OverviewCalendarEvent(
        event_type=OverviewCalendarEventType.FILING,
        event_date=date(2025, 4, 15),
        source="filed_declarations",
        summary="Observed filing",
        reference_id=f"aeat-{modelo}-{period.registry_token}",
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        status="ALTA",
        authenticated_identity="X1234567L",
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        aeat_submitted_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        justificante_verified=False,
    )


@pytest.mark.parametrize(
    ("state", "value", "message"),
    [
        (_state(HomeAvailability.AVAILABLE), None, "requires its loaded source bundle"),
        (
            _state(HomeAvailability.LOCKED),
            CalendarEvidenceSources(),
            "cannot carry source values",
        ),
    ],
)
def test_read_outcome_refuses_state_value_mismatches(
    state: HomeZoneState,
    value: CalendarEvidenceSources | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        CalendarEvidenceReadOutcome(state=state, value=value)


def test_stale_local_values_and_their_source_timestamp_are_preserved() -> None:
    projection = build_calendar_evidence_projection(
        local=_local(HomeAvailability.STALE, records=(modelo_record(),), observed_at=_OBSERVED_AT),
        aeat=_aeat(HomeAvailability.NEVER_CAPTURED),
    )

    assert projection.local_state.availability is HomeAvailability.STALE
    assert projection.local_state.observed_at == _OBSERVED_AT
    assert projection.aeat_state.availability is HomeAvailability.NEVER_CAPTURED
    assert len(projection.evidence) == 1
    row = projection.evidence[0]
    assert row.local_filing_record_id is not None
    assert row.local_filed_at == datetime(2025, 4, 14, 12, 0, tzinfo=UTC)
    assert row.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED


def test_never_captured_evidence_remains_unknown_instead_of_becoming_available_empty() -> None:
    projection = build_calendar_evidence_projection(
        local=_local(HomeAvailability.LOCKED),
        aeat=_aeat(HomeAvailability.NEVER_CAPTURED),
    )

    assert projection.evidence == ()
    assert projection.local_state.reason_code == "evidence.locked"
    assert projection.aeat_state.reason_code == "evidence.never_captured"


def test_natural_address_join_is_deterministic_and_preserves_both_axes() -> None:
    period_2t = Period.from_year_and_code(2025, "2T")
    records = (
        modelo_record(modelo="303", period=period_2t),
        modelo_record(modelo="130", period=_PERIOD),
    )
    events = (_observed_event(modelo="303", period=period_2t), _observed_event(modelo="130"))

    forward = build_calendar_evidence_projection(
        local=_local(records=records),
        aeat=_aeat(events=events),
        expected_tax_id="X1234567L",
    )
    reversed_sources = build_calendar_evidence_projection(
        local=_local(records=tuple(reversed(records))),
        aeat=_aeat(events=tuple(reversed(events))),
        expected_tax_id="X1234567L",
    )

    assert reversed_sources.evidence == forward.evidence
    assert [
        (row.modelo, row.filing_year, row.period.registry_token if row.period is not None else None)
        for row in forward.evidence
    ] == [("130", 2025, "1T"), ("303", 2025, "2T")]
    assert all(row.local_filing_record_id is not None for row in forward.evidence)
    assert all(row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED for row in forward.evidence)


def test_provider_performs_no_implicit_file_or_network_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the evidence provider attempted implicit I/O")

    monkeypatch.setattr(builtins, "open", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    projection = build_calendar_evidence_projection(local=_local(), aeat=_aeat())

    assert projection.evidence == ()
