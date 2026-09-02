"""Contract tests for the frontend-neutral overview evidence provider."""

from __future__ import annotations

import builtins
import socket
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from ....core.period import Period
from ....domain.modelos.filing_record import ExternalEvidenceKind, ModeloRecord
from ..calendar_models import OverviewAeatSubmissionState, OverviewCalendarEvent, OverviewCalendarEventType
from ..evidence import (
    AeatCalendarEvidenceSources,
    CalendarEvidenceReadOutcome,
    LocalCalendarEvidenceSources,
    build_calendar_evidence_projection,
)
from ..home import HomeAvailability, HomeZoneState
from .calendar_test_support import external_evidence, modelo_record

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
    records: tuple[ModeloRecord, ...] = (),
    observed_at: datetime | None = None,
) -> CalendarEvidenceReadOutcome[LocalCalendarEvidenceSources]:
    return CalendarEvidenceReadOutcome(
        state=_state(availability, observed_at=observed_at),
        value=(
            LocalCalendarEvidenceSources(filing_records=records)
            if availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}
            else None
        ),
    )


def _aeat(
    availability: HomeAvailability = HomeAvailability.AVAILABLE,
    *,
    records: tuple[ModeloRecord, ...] = (),
    events: tuple[OverviewCalendarEvent, ...] = (),
    observed_at: datetime | None = None,
) -> CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]:
    return CalendarEvidenceReadOutcome(
        state=_state(availability, observed_at=observed_at),
        value=(
            AeatCalendarEvidenceSources(filing_records=records, observed_events=events)
            if availability in {HomeAvailability.AVAILABLE, HomeAvailability.STALE}
            else None
        ),
    )


def _observed_event(
    *,
    modelo: str = "303",
    period: Period = _PERIOD,
    reference_id: str | None = None,
    submitted_at: datetime | None = None,
    authenticated_identity: str | None = "X1234567L",
) -> OverviewCalendarEvent:
    return OverviewCalendarEvent(
        event_type=OverviewCalendarEventType.FILING,
        event_date=date(2025, 4, 15),
        source="filed_declarations",
        summary="Observed filing",
        reference_id=reference_id or f"aeat-{modelo}-{period.registry_token}",
        modelo=modelo,
        filing_year=period.filing_year,
        period=period,
        status="ALTA",
        authenticated_identity=authenticated_identity,
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        aeat_submitted_at=submitted_at or datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
        justificante_verified=False,
    )


@pytest.mark.parametrize(
    ("state", "value", "message"),
    [
        (_state(HomeAvailability.AVAILABLE), None, "requires its loaded source bundle"),
        (
            _state(HomeAvailability.LOCKED),
            LocalCalendarEvidenceSources(),
            "cannot carry source values",
        ),
    ],
)
def test_read_outcome_refuses_state_value_mismatches(
    state: HomeZoneState,
    value: LocalCalendarEvidenceSources | None,
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


def test_local_records_cannot_establish_the_aeat_axis_without_an_aeat_read() -> None:
    record = modelo_record(
        aeat_accepted=True,
        external_evidence=external_evidence(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, "CSVLOCAL30320251T"),
    )

    projection = build_calendar_evidence_projection(
        local=_local(records=(record,)),
        aeat=_aeat(HomeAvailability.NEVER_CAPTURED),
        expected_tax_id="X1234567L",
    )

    assert len(projection.evidence) == 1
    assert projection.evidence[0].local_filing_record_id is not None
    assert projection.evidence[0].aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED


def test_aeat_records_do_not_establish_the_local_axis_when_local_is_available_empty() -> None:
    record = modelo_record(
        aeat_accepted=True,
        external_evidence=external_evidence(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, "CSVAEAT30320251T"),
    )

    projection = build_calendar_evidence_projection(
        local=_local(),
        aeat=_aeat(records=(record,)),
        expected_tax_id="X1234567L",
    )

    assert len(projection.evidence) == 1
    assert projection.evidence[0].local_filing_record_id is None
    assert projection.evidence[0].aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED


def test_never_captured_evidence_remains_unknown_instead_of_becoming_available_empty() -> None:
    projection = build_calendar_evidence_projection(
        local=_local(HomeAvailability.LOCKED),
        aeat=_aeat(HomeAvailability.NEVER_CAPTURED),
    )

    assert projection.evidence == ()
    assert projection.local_state.reason_code == "evidence.locked"
    assert projection.aeat_state.reason_code == "evidence.never_captured"


def test_available_empty_and_never_captured_remain_distinct_source_states() -> None:
    available_empty = build_calendar_evidence_projection(local=_local(), aeat=_aeat())
    never_captured = build_calendar_evidence_projection(
        local=_local(),
        aeat=_aeat(HomeAvailability.NEVER_CAPTURED),
    )

    assert available_empty.evidence == never_captured.evidence == ()
    assert available_empty.aeat_state.availability is HomeAvailability.AVAILABLE
    assert never_captured.aeat_state.availability is HomeAvailability.NEVER_CAPTURED


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


def test_equal_strength_same_address_claims_have_a_deterministic_primary_reference() -> None:
    earlier = _observed_event(
        reference_id="AEAT-REF-A",
        submitted_at=datetime(2025, 4, 15, 9, 0, tzinfo=UTC),
    )
    later = _observed_event(
        reference_id="AEAT-REF-B",
        submitted_at=datetime(2025, 4, 15, 10, 0, tzinfo=UTC),
    )

    forward = build_calendar_evidence_projection(local=_local(), aeat=_aeat(events=(earlier, later)))
    reverse = build_calendar_evidence_projection(local=_local(), aeat=_aeat(events=(later, earlier)))

    assert reverse.evidence == forward.evidence
    assert len(forward.evidence) == 1
    assert forward.evidence[0].aeat_reference_id == "AEAT-REF-B"
    assert forward.evidence[0].aeat_evidence_conflict_reference_ids == ("AEAT-REF-A", "AEAT-REF-B")


@pytest.mark.parametrize(
    ("authenticated_identity", "expected_tax_id", "is_retained"),
    [
        ("X1234567L", "X1234567L", True),
        ("Y7654321G", "X1234567L", False),
        (None, "X1234567L", False),
        (None, None, True),
    ],
)
def test_aeat_event_identity_match_mismatch_and_absence(
    authenticated_identity: str | None,
    expected_tax_id: str | None,
    is_retained: bool,
) -> None:
    projection = build_calendar_evidence_projection(
        local=_local(),
        aeat=_aeat(events=(_observed_event(authenticated_identity=authenticated_identity),)),
        expected_tax_id=expected_tax_id,
    )

    assert bool(projection.evidence) is is_retained


def test_provider_refuses_a_runtime_source_bundle_on_the_wrong_axis() -> None:
    wrong_local = cast(
        Any,
        CalendarEvidenceReadOutcome(
            state=_state(HomeAvailability.AVAILABLE),
            value=AeatCalendarEvidenceSources(),
        ),
    )

    with pytest.raises(TypeError, match="local evidence outcome"):
        build_calendar_evidence_projection(local=wrong_local, aeat=_aeat())


def test_provider_performs_no_implicit_file_or_network_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the evidence provider attempted implicit I/O")

    monkeypatch.setattr(builtins, "open", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    projection = build_calendar_evidence_projection(local=_local(), aeat=_aeat())

    assert projection.evidence == ()
