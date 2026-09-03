"""Contract tests for the safe Declarations full-calendar projection."""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast

import pytest

from ....core.identity import CalculationRevisionId, FilingRecordId, WorkUnitId
from ....core.period import Period
from ....domain.deadlines.models import ObligationStatus
from ...overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEntrySource,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
)
from ...overview.evidence import CalendarEvidenceProjection
from ...overview.home import HomeAvailability, HomeZoneState
from ...overview.next_actions import declare_next_action
from ..declarations_calendar import (
    DeclarationsCalendarProjectionError,
    DeclarationsCalendarSource,
    DeclarationsCalendarSourceObservationV1,
    project_declarations_calendar,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 3, 10, tzinfo=UTC)
_RANGE = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))
_WORK = cast("WorkUnitId", "a" * 64)
_REVISION = cast("CalculationRevisionId", "b" * 64)
_FILING = cast("FilingRecordId", "c" * 64)


def _state(
    availability: HomeAvailability = HomeAvailability.AVAILABLE,
    *,
    observed_at: datetime | None = None,
) -> HomeZoneState:
    return HomeZoneState(
        availability=availability,
        observed_at=observed_at,
        reason_code=None if availability is HomeAvailability.AVAILABLE else f"calendar.{availability.value}",
    )


def _schedule(
    availability: HomeAvailability = HomeAvailability.AVAILABLE,
    *,
    observed_at: datetime | None = None,
) -> DeclarationsCalendarSourceObservationV1:
    return DeclarationsCalendarSourceObservationV1(
        source=DeclarationsCalendarSource.SCHEDULE,
        availability=availability,
        observed_at=observed_at,
        reason_code=None if availability is HomeAvailability.AVAILABLE else f"calendar.{availability.value}",
    )


def _filing_evidence(
    *,
    modelo: str = "303",
    period: Period | None = None,
    local: OverviewLocalFilingState = OverviewLocalFilingState.NOT_READY_TO_FILE,
    aeat: OverviewAeatSubmissionState = OverviewAeatSubmissionState.NOT_OBSERVED,
) -> OverviewCalendarFilingEvidence:
    resolved_period = period or Period.from_year_and_code(2026, "1T")
    verified = aeat is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    return OverviewCalendarFilingEvidence(
        modelo=modelo,
        filing_year=resolved_period.filing_year,
        period=resolved_period,
        local_filing_state=local,
        local_filing_record_id=_FILING if local is not OverviewLocalFilingState.NOT_READY_TO_FILE else None,
        local_calculation_revision_id=_REVISION if local is not OverviewLocalFilingState.NOT_READY_TO_FILE else None,
        aeat_submission_state=aeat,
        aeat_reference_id="private-aeat-reference" if aeat is not OverviewAeatSubmissionState.NOT_OBSERVED else None,
        aeat_snapshot_id="d" * 64 if aeat is not OverviewAeatSubmissionState.NOT_OBSERVED else None,
        aeat_evidence_kind="private-source-kind" if aeat is not OverviewAeatSubmissionState.NOT_OBSERVED else None,
        verified_justificante_csv="ABCDEF1234567890" if verified else None,
        justificante_verified=verified,
    )


def _entry(
    *,
    modelo: str = "303",
    period: Period | None = None,
    close: date = date(2026, 4, 20),
    evidence: OverviewCalendarFilingEvidence | None = None,
) -> OverviewCalendarEntry:
    resolved_period = period or Period.from_year_and_code(2026, "1T")
    return OverviewCalendarEntry(
        modelo=modelo,
        period=resolved_period,
        opens_on=close.replace(day=1),
        closes_on=close,
        adjusted_closes_on=close,
        shift_reason="none",
        status=ObligationStatus.UPCOMING,
        user_state=OverviewPeriodState.DUE,
        filing_year=resolved_period.filing_year,
        filing_evidence=evidence or _filing_evidence(modelo=modelo, period=resolved_period),
        source=OverviewCalendarEntrySource.REGISTRY_DEADLINE,
        local_work_unit_id=_WORK,
        local_work_unit_name="Private taxpayer declaration label",
        local_work_unit_revision_id="private-registry-revision",
    )


def _calendar(*entries: OverviewCalendarEntry) -> OverviewCalendar:
    return OverviewCalendar(
        range=_RANGE,
        entries=entries,
        generated_at=_NOW,
        events=(
            OverviewCalendarEvent(
                event_type=OverviewCalendarEventType.MESSAGE,
                event_date=date(2026, 4, 21),
                source="private-source",
                summary="Private event prose and taxpayer facts",
                reference_id="private-event-reference",
            ),
        ),
    )


def _provider(
    *rows: OverviewCalendarFilingEvidence,
    local: HomeAvailability = HomeAvailability.AVAILABLE,
    aeat: HomeAvailability = HomeAvailability.AVAILABLE,
    observed_at: datetime | None = None,
) -> CalendarEvidenceProjection:
    return CalendarEvidenceProjection(
        local_state=_state(local, observed_at=observed_at),
        aeat_state=_state(aeat, observed_at=observed_at),
        evidence=rows,
    )


def test_exact_source_axis_matrix_and_safe_full_row_are_preserved() -> None:
    evidence = _filing_evidence(
        local=OverviewLocalFilingState.READY_TO_FILE,
        aeat=OverviewAeatSubmissionState.ACCEPTED,
    )
    entry = _entry(evidence=evidence)
    action = declare_next_action("operator.modelo.work.create", modelo="303", year=2026, period="1T")
    entry = entry.model_copy(update={"recovery": object(), "recovery_action": action})
    projection = project_declarations_calendar(
        calendar=_calendar(entry),
        evidence=_provider(evidence),
        as_of=date(2026, 3, 1),
        schedule_observation=_schedule(),
    )

    assert tuple((source.source, source.availability, source.item_count) for source in projection.sources) == (
        (DeclarationsCalendarSource.SCHEDULE, HomeAvailability.AVAILABLE, 1),
        (DeclarationsCalendarSource.LOCAL_FILING, HomeAvailability.AVAILABLE, 1),
        (DeclarationsCalendarSource.AEAT_EVIDENCE, HomeAvailability.AVAILABLE, 1),
    )
    row = projection.entries[0]
    assert row.semantic_key() == ("303", 2026, "1T")
    assert (row.opens_on, row.adjusted_closes_on, row.payment_cutoff_on) == (
        date(2026, 4, 1),
        date(2026, 4, 20),
        None,
    )
    assert row.legal_status is ObligationStatus.UPCOMING
    assert row.user_state is OverviewPeriodState.DUE
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED
    assert row.justificante_verified is False
    assert row.source is OverviewCalendarEntrySource.REGISTRY_DEADLINE
    assert row.recovery_action == action
    assert "operator.modelo.work.create" not in projection.model_dump_json()


def test_projection_strips_every_protected_identity_name_event_and_reference() -> None:
    evidence = _filing_evidence(
        local=OverviewLocalFilingState.READY_TO_FILE,
        aeat=OverviewAeatSubmissionState.ACCEPTED,
    )
    projection = project_declarations_calendar(
        calendar=_calendar(_entry(evidence=evidence)),
        evidence=_provider(evidence),
        as_of=date(2026, 3, 1),
        schedule_observation=_schedule(),
    )
    exposed = projection.model_dump_json() + repr(projection)
    for secret in (
        _WORK,
        _REVISION,
        _FILING,
        "Private taxpayer declaration label",
        "private-registry-revision",
        "private-aeat-reference",
        "d" * 64,
        "ABCDEF1234567890",
        "private-source-kind",
        "Private event prose and taxpayer facts",
        "private-event-reference",
    ):
        assert secret not in exposed


def test_known_not_observed_and_unobservable_aeat_are_distinct() -> None:
    entry = _entry()
    known = project_declarations_calendar(
        calendar=_calendar(entry),
        evidence=_provider(),
        as_of=date(2026, 3, 1),
        schedule_observation=_schedule(),
    )
    unknown = project_declarations_calendar(
        calendar=_calendar(entry),
        evidence=_provider(aeat=HomeAvailability.NEVER_CAPTURED),
        as_of=date(2026, 3, 1),
        schedule_observation=_schedule(),
    )
    assert known.entries[0].aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED
    assert known.entries[0].justificante_verified is False
    assert unknown.entries[0].aeat_submission_state is None
    assert unknown.entries[0].justificante_verified is None
    assert unknown.sources[-1].item_count is None


def test_known_empty_unavailable_and_stale_are_not_conflated() -> None:
    known_empty = project_declarations_calendar(
        calendar=_calendar(),
        evidence=_provider(),
        as_of=date(2026, 3, 1),
        schedule_observation=_schedule(),
    )
    unavailable = project_declarations_calendar(
        calendar=_calendar(),
        evidence=_provider(local=HomeAvailability.UNAVAILABLE, aeat=HomeAvailability.LOCKED),
        as_of=date(2026, 3, 1),
        schedule_observation=_schedule(HomeAvailability.UNAVAILABLE),
    )
    stale_evidence = _filing_evidence(aeat=OverviewAeatSubmissionState.ACCEPTED)
    stale = project_declarations_calendar(
        calendar=_calendar(_entry(evidence=stale_evidence)),
        evidence=_provider(stale_evidence, aeat=HomeAvailability.STALE, observed_at=_NOW),
        as_of=date(2026, 3, 1),
        schedule_observation=_schedule(HomeAvailability.STALE, observed_at=_NOW),
    )
    assert known_empty.sources[0].item_count == 0
    assert unavailable.sources[0].item_count is None
    assert stale.entries[0].aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED
    assert stale.sources[-1].observed_at == _NOW


@pytest.mark.parametrize(
    "case",
    (
        "duplicate_entry",
        "partial_evidence_address",
        "local_unobservable_claim",
        "aeat_unobservable_claim",
        "local_authority_mismatch",
        "aeat_authority_mismatch",
        "wrong_recovery_address",
        "unavailable_schedule_rows",
    ),
)
def test_contradictory_inputs_fail_closed(case: str) -> None:
    evidence = _filing_evidence(
        local=OverviewLocalFilingState.READY_TO_FILE,
        aeat=OverviewAeatSubmissionState.ACCEPTED,
    )
    entry = _entry(evidence=evidence)
    calendar = _calendar(entry)
    provider = _provider(evidence)
    schedule = _schedule()
    if case == "duplicate_entry":
        calendar = _calendar(entry, entry)
    elif case == "partial_evidence_address":
        partial = OverviewCalendarFilingEvidence(modelo="303")
        provider = _provider(partial)
        calendar = _calendar(_entry())
    elif case == "local_unobservable_claim":
        provider = _provider(local=HomeAvailability.LOCKED)
    elif case == "aeat_unobservable_claim":
        provider = _provider(aeat=HomeAvailability.NEVER_CAPTURED)
    elif case == "local_authority_mismatch":
        provider = _provider(_filing_evidence(aeat=OverviewAeatSubmissionState.ACCEPTED))
    elif case == "aeat_authority_mismatch":
        provider = _provider(_filing_evidence(local=OverviewLocalFilingState.READY_TO_FILE))
    elif case == "wrong_recovery_address":
        action = declare_next_action("operator.modelo.work.create", modelo="130", year=2026, period="1T")
        calendar = _calendar(entry.model_copy(update={"recovery": object(), "recovery_action": action}))
    elif case == "unavailable_schedule_rows":
        schedule = _schedule(HomeAvailability.UNAVAILABLE)
    with pytest.raises(DeclarationsCalendarProjectionError):
        project_declarations_calendar(
            calendar=calendar,
            evidence=provider,
            as_of=date(2026, 3, 1),
            schedule_observation=schedule,
        )


def test_order_is_deterministic_by_deadline_then_natural_identity() -> None:
    rows = (
        _entry(modelo="303", close=date(2026, 4, 20)),
        _entry(modelo="130", close=date(2026, 4, 20)),
        _entry(modelo="111", period=Period.from_year_and_code(2026, "01"), close=date(2026, 2, 20)),
    )
    forward = project_declarations_calendar(
        calendar=_calendar(*rows),
        evidence=_provider(),
        as_of=date(2026, 1, 1),
        schedule_observation=_schedule(),
    )
    reverse = project_declarations_calendar(
        calendar=_calendar(*reversed(rows)),
        evidence=_provider(),
        as_of=date(2026, 1, 1),
        schedule_observation=_schedule(),
    )
    assert forward == reverse
    assert tuple(row.semantic_key() for row in forward.entries) == (
        ("111", 2026, "01"),
        ("130", 2026, "1T"),
        ("303", 2026, "1T"),
    )


def test_defining_module_has_no_io_adapter_entrypoint_or_network_import() -> None:
    path = Path(__file__).parents[1] / "declarations_calendar.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not any(
        forbidden in imported
        for imported in imports
        for forbidden in ("adapters", "entrypoints", "pathlib", "requests", "httpx", "socket")
    )
    assert calls.isdisjoint({"open", "print", "input", "read", "write"})
