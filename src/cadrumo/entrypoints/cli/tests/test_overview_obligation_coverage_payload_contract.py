"""Contract parity for overview obligation-coverage transport."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....application.overview import (
    AdvisedObligation,
    CoverageAdviceReason,
    ObligationCoverageReport,
    OverviewCalendar,
    OverviewCalendarRange,
)
from ....application.overview._agenda import OverviewAgenda
from ....application.overview._backlog import OverviewBacklog
from .._overview_payloads import (
    OverviewAgendaResult,
    OverviewBacklogResult,
    OverviewCalendarPayload,
    OverviewCalendarProfilePayload,
    OverviewCalendarResult,
)
from .._overview_rendering import (
    overview_agenda_output,
    overview_backlog_output,
    overview_calendar_output,
    overview_calendar_profile_output,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _coverage_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "surfaced": ["303"],
        "confidently_excluded": ["100"],
        "advised": [{"modelo": "190", "reason": "applicable_window_missing"}],
        "out_of_scope": ["037"],
    }
    payload.update(overrides)
    return payload


def _calendar_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "range": {"from_date": "2026-01-01", "to_date": "2026-03-31"},
        "entries": [],
        "generated_at": "2026-01-01T00:00:00Z",
        "warnings": [],
        "completeness": {},
        "taxpayer_model_declared": True,
        "coverage": _coverage_payload(),
    }
    payload.update(overrides)
    return payload


def test_calendar_coverage_refuses_omission_and_overlapping_dispositions() -> None:
    """Coverage cannot vanish or name one modelo in multiple dispositions."""
    without_coverage = _calendar_payload()
    without_coverage.pop("coverage")
    with pytest.raises(ValidationError):
        OverviewCalendarPayload.model_validate(without_coverage)
    with pytest.raises(ValidationError):
        OverviewCalendarPayload.model_validate(
            _calendar_payload(
                coverage=_coverage_payload(advised=[{"modelo": "303", "reason": "applicable_window_missing"}])
            ),
        )


def test_single_calendar_and_derived_surfaces_require_coverage() -> None:
    """The single-calendar, agenda, and backlog envelopes reject omitted coverage."""
    without_coverage = _calendar_payload()
    without_coverage.pop("coverage")
    with pytest.raises(ValidationError):
        OverviewCalendarResult.model_validate(without_coverage)
    with pytest.raises(ValidationError):
        OverviewAgendaResult.model_validate({})
    with pytest.raises(ValidationError):
        OverviewBacklogResult.model_validate({})


def test_calendar_rendering_round_trips_the_canonical_coverage_partition() -> None:
    """The renderer retains every canonical coverage bucket in its JSON result."""
    calendar_range = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 3, 31))
    coverage = ObligationCoverageReport(
        surfaced=("303",),
        confidently_excluded=("100",),
        advised=(
            AdvisedObligation(
                modelo="190",
                reason=CoverageAdviceReason.APPLICABLE_WINDOW_MISSING,
            ),
        ),
        out_of_scope=("037",),
    )
    calendar = OverviewCalendar(
        range=calendar_range,
        entries=(),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        coverage=coverage,
    )

    rendered, lines, notices = overview_calendar_output(calendar, calendar_range, evidence_notices=())

    assert rendered.coverage is not None
    assert rendered.coverage.model_dump(mode="json") == coverage.model_dump(mode="json")
    assert any(line.startswith("coverage_advised\t1\t") for line in lines)
    assert notices[0].context == {"190": "applicable_window_missing"}


def test_every_calendar_derived_renderer_retains_coverage() -> None:
    """Calendar profiles, agenda, and backlog preserve the same coverage JSON."""
    calendar_range = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 3, 31))
    coverage = ObligationCoverageReport(
        advised=(AdvisedObligation(modelo="190", reason=CoverageAdviceReason.REGISTRY_UNMODELED),),
    )
    calendar = OverviewCalendar(
        range=calendar_range,
        entries=(),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        coverage=coverage,
    )
    profile, _, _ = overview_calendar_profile_output(bucket_id="bucket-1", label="Operator", cal=calendar)
    agenda, _, _ = overview_agenda_output(
        OverviewAgenda(
            as_of=date(2026, 1, 1),
            horizon_days=14,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            coverage=coverage,
        ),
    )
    backlog, _, _ = overview_backlog_output(
        OverviewBacklog(
            range=calendar_range,
            as_of=date(2026, 1, 1),
            late_count=0,
            generated_at=datetime(2026, 1, 1, tzinfo=UTC),
            coverage=coverage,
        ),
        work_units_notice=None,
    )

    expected = coverage.model_dump(mode="json")
    assert OverviewCalendarProfilePayload.model_validate(profile).calendar.coverage.model_dump(mode="json") == expected
    assert agenda.coverage.model_dump(mode="json") == expected
    assert backlog.coverage.model_dump(mode="json") == expected
