"""Contract parity for overview obligation-coverage transport."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....application.overview.agenda import OverviewAgenda
from ....application.overview.backlog import OverviewBacklog
from ....application.overview.calendar_evidence import NO_AEAT_HISTORY_NOTICE_CODE
from ....application.overview.calendar_models import OverviewCalendar, OverviewCalendarRange
from ....application.overview.coverage import AdvisedObligation, CoverageAdviceReason, ObligationCoverageReport
from ....core.json_contract import Notice, NoticeSeverity, ResolvedNoticeAction
from .._overview_payloads import (
    OverviewAgendaResult,
    OverviewBacklogResult,
    OverviewCalendarProfilePayload,
    OverviewCalendarResult,
)
from .._overview_rendering import (
    overview_agenda_output,
    overview_backlog_output,
    overview_calendar_output,
    overview_calendar_profile_output,
    overview_coverage_notices,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

#: A profile identifier is a UUIDv4 -- the shape production mints and the only
#: shape the payload contract accepts.
_PROFILE_ID = "44450001-0000-4000-8000-000000000001"


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


def test_calendar_coverage_cannot_vanish_from_the_envelope() -> None:
    """Coverage is a required part of the calendar envelope, never omitted.

    The companion invariant -- that one modelo cannot occupy two dispositions --
    is enforced by the canonical
    :class:`~application.overview.ObligationCoverageReport`, which refuses to
    construct such a partition at all, so every consumer inherits it and not
    only this JSON surface. It is pinned in that model's own test module; the
    transport contract is the shape of a report that already satisfies it.
    """
    without_coverage = _calendar_payload()
    without_coverage.pop("coverage")
    with pytest.raises(ValidationError):
        OverviewCalendarResult.model_validate(without_coverage)


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
    assert rendered.generated_at == "2026-01-01T00:00:00+00:00"
    assert rendered.completeness is not None
    assert rendered.taxpayer_model_declared is True
    assert rendered.incomplete_reason is None
    assert any(line.startswith("coverage_advised\t1\t") for line in lines)
    assert notices[0].context == {"modelo": "190", "reason": "applicable_window_missing"}
    notice_action = notices[0].action
    assert isinstance(notice_action, ResolvedNoticeAction)
    assert notice_action.action.action_id == "operator.overview.explain"
    assert notice_action.action.target_command_key == "overview.explain"
    assert notice_action.argument_bindings[0].value == "190"


def test_coverage_notices_bind_one_modelo_per_explanation_action() -> None:
    """Every coverage notice carries only the modelo its action can execute."""
    coverage = ObligationCoverageReport(
        advised=(
            AdvisedObligation(modelo="130", reason=CoverageAdviceReason.APPLICABILITY_UNDETERMINED),
            AdvisedObligation(modelo="190", reason=CoverageAdviceReason.APPLICABLE_WINDOW_MISSING),
        ),
    )

    notices = overview_coverage_notices(coverage)

    by_modelo = {notice.context["modelo"]: notice for notice in notices if notice.context is not None}
    assert set(by_modelo) == set(coverage.advised_modelos)
    for modelo, notice in by_modelo.items():
        notice_action = notice.action
        assert isinstance(notice_action, ResolvedNoticeAction)
        assert notice_action.action.action_id == "operator.overview.explain"
        assert notice_action.argument_bindings[0].value == modelo


def test_calendar_projection_resolves_the_history_pull_action() -> None:
    """The application history finding becomes executable only at the CLI boundary."""
    calendar_range = OverviewCalendarRange(from_date=date(2026, 1, 1), to_date=date(2026, 3, 31))
    calendar = OverviewCalendar(
        range=calendar_range,
        entries=(),
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    application_notice = Notice(
        severity=NoticeSeverity.INFO,
        code=NO_AEAT_HISTORY_NOTICE_CODE,
        message="No official filing history is available for this profile.",
        context={"observation_count": "0"},
    )

    _, _, notices = overview_calendar_output(calendar, calendar_range, evidence_notices=(application_notice,))

    assert len(notices) == 1
    notice_action = notices[0].action
    assert isinstance(notice_action, ResolvedNoticeAction)
    assert notice_action.action.action_id == "operator.live.filed.pull_all"
    assert notice_action.action.target_command_key == "app.live.filed.pull_all"
    assert notice_action.argument_bindings == ()


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
    profile, _, profile_notices = overview_calendar_profile_output(
        bucket_id=_PROFILE_ID,
        label="Operator",
        cal=calendar,
    )
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
    assert agenda.coverage.model_dump(mode="json") == expected
    assert backlog.coverage.model_dump(mode="json") == expected
    # The all-profiles block is a per-profile SUMMARY and no longer embeds the
    # calendar, so coverage reaches a machine consumer there on the notice
    # channel instead. The structured advised map rides on ``Notice.context``,
    # so nothing about the advisory became unreadable -- it moved surfaces.
    summary = OverviewCalendarProfilePayload.model_validate(profile)
    assert summary.profile_id == _PROFILE_ID
    advised_contexts = [notice.context or {} for notice in profile_notices]
    assert any(context.get("modelo") == item.modelo for item in coverage.advised for context in advised_contexts), (
        f"the profile path must still surface every advised modelo; notices carried {advised_contexts}"
    )
