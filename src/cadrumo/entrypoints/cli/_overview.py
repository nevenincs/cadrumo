"""CLI transport for authenticated overview reads and pipeline health."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

import typer

from ...application.cli_exception_preconditions import (
    CliExceptionPrecondition,
    cli_exception_no_recovery_verdict,
)
from ...application.operations.public_period import PublicPeriod
from ...application.operator_actions.models import ActionReference
from ...application.overview.read_payload import (
    OverviewAgendaRead,
    OverviewBacklogRead,
    OverviewCalendarRead,
    OverviewExplainRead,
    OverviewPrepareRead,
    OverviewStatusRead,
)
from ...application.overview.read_projection import OverviewNoticeSnapshot
from ...application.overview.read_request import OverviewReadKind, OverviewReadRequest
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as current_output_language
from ...core.i18n.render import tr
from ...core.json_contract import Notice, strict_round_trip
from ...core.period import Period, PeriodError
from ...core.time.clock import today_madrid
from ._date_parsing import _parse_iso_date
from ._overview_payloads import OverviewCalendarResult, OverviewDraftPayload, OverviewStatusResult
from ._overview_rendering import (
    overview_agenda_output,
    overview_backlog_output,
    overview_calendar_output,
    overview_calendar_profile_output,
    overview_coverage_notices,
    overview_explain_output,
    overview_pipeline_output,
    overview_prepare_output,
    overview_status_output,
)
from .common import (
    activate_subcommand_output_language,
    attach_cli_policy_verdict,
    bad,
    emit_envelope,
    resolve_notice_action,
)
from .errors import CliRefusedBoundaryError
from .period_parsing import _canonical_period
from .registered_operation_errors import submitted_operation_error
from .runtime_overview import OverviewReadCompletion, read_overview
from .runtime_overview_pipeline import read_overview_pipeline


def _request(kind: OverviewReadKind, **fields: object) -> OverviewReadRequest:
    """Bind one query to the selected profile and current output language."""
    return OverviewReadRequest.model_validate(
        {
            "profile_id": UUID(require_active_bucket_id()),
            "kind": kind,
            "output_language": OutputLanguage(current_output_language()),
            **fields,
        }
    )


def _notice(snapshot: OverviewNoticeSnapshot) -> Notice:
    """Materialise a declared action against the live CLI only after disclosure."""
    return Notice(
        severity=snapshot.severity,
        code=snapshot.code,
        message=snapshot.message,
        context=dict(snapshot.context),
        action=(
            resolve_notice_action(action=ActionReference(action_id=snapshot.action_id))
            if snapshot.action_id is not None
            else None
        ),
    )


def _emit_read[T](completed: OverviewReadCompletion, render: Callable[[], T]) -> T:
    """Keep the successful worker receipt if local rendering or output fails."""
    try:
        return render()
    except typer.Exit:
        raise
    except CliRefusedBoundaryError:
        raise
    except Exception:
        receipt = completed.completion
        raise submitted_operation_error(
            receipt.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=receipt.terminal_condition,
            effect=receipt.effect,
            refusal_code=receipt.refusal_code,
        ) from None


def _incomplete_refusal(
    completed: OverviewReadCompletion, requirements: tuple[str, ...], *, undeclared: bool, warning_count: int
) -> CliRefusedBoundaryError:
    """Retain known operation identity while refusing an incomplete profile."""
    receipt = completed.completion
    return attach_cli_policy_verdict(
        CliRefusedBoundaryError(
            translated_message=(
                "cli.overview.refused_undeclared_taxpayer_model"
                if undeclared
                else "cli.overview.refused_incomplete_profile"
            ),
            context={
                "requirements": ", ".join(requirements),
                "operation_id": str(receipt.operation_id),
                "terminal_condition": receipt.terminal_condition.value,
                "effect": receipt.effect.value,
            },
        ),
        verdict=cli_exception_no_recovery_verdict(
            CliExceptionPrecondition.OVERVIEW_PROFILE_COMPLETE,
            facts={"missing_selector_count" if undeclared else "warning_count": warning_count},
        ),
    )


def _overview_status_period(period: str, *, year: int | None) -> Period:
    """Resolve a period status selector through the canonical period union."""
    token = period.strip()
    if not token:
        raise bad(tr("cli.common.errors.period_empty"))
    if year is None:
        raise bad(tr("cli.common.errors.period_missing_year", token=token))
    try:
        return Period.from_year_and_code(year, token)
    except PeriodError as exc:
        raise bad(tr("cli.common.errors.period_unrecognised", raw=period)) from exc


def overview_status(
    ctx: typer.Context, period: str | None = None, year: int | None = None, verbose: bool = False
) -> None:
    """Render the selected profile's recorded workspace or exact period status."""
    query = _request(
        OverviewReadKind.STATUS,
        **(
            {"period": PublicPeriod.from_period(_overview_status_period(period, year=year)), "verbose": verbose}
            if period is not None
            else {"verbose": verbose}
        ),
    )
    completed = read_overview(ctx, request=query)

    def render() -> None:
        payload = completed.payload
        if not isinstance(payload, OverviewStatusRead):
            raise ValueError("overview status projection has the wrong kind")
        if payload.period_report is not None:
            exact = payload.period_report
            canonical = exact.period.to_period()
            drafts = [
                OverviewDraftPayload(draft_id=row.draft_id, modelo=row.modelo, status=row.status)
                for row in exact.drafts
            ]
            typed = OverviewStatusResult(period=str(canonical), drafts=drafts, verbose=exact.verbose)
            lines = [
                f"{tr('cli.overview.period')}\t{canonical}",
                f"{tr('cli.overview.drafts')}\t{len(drafts)}",
                *(f"{row.modelo}\t{row.draft_id}\t{row.status}" for row in drafts),
            ]
            emit_envelope(ctx, command="overview.status", result=typed, lines=lines)
            return
        if payload.report is None:
            raise ValueError("overview full status report is missing")
        report = payload.report.to_report()
        typed = strict_round_trip(OverviewStatusResult, report)
        lines, notices = overview_status_output(report)
        if payload.coverage is not None:
            for notice in overview_coverage_notices(payload.coverage):
                notices.append(notice)
                lines.append(f"coverage_advised\t{payload.coverage_advised_count}\t{notice.message}")
        notices.extend(_notice(item) for item in payload.notices)
        emit_envelope(ctx, command="overview.status", result=typed, lines=lines, notices=notices)

    _emit_read(completed, render)


def overview_calendar(
    ctx: typer.Context,
    from_date: str,
    to_date: str,
    allow_incomplete: bool = False,
    show_suppressed: bool = False,
    all_profiles: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Render a captured deadline calendar or public locked-profile survey."""
    activate_subcommand_output_language(ctx, output_language)
    query = _request(
        OverviewReadKind.CALENDAR,
        from_date=_parse_iso_date(from_date, label="--from"),
        to_date=_parse_iso_date(to_date, label="--to"),
        allow_incomplete=allow_incomplete,
        show_suppressed=show_suppressed,
        all_profiles=all_profiles,
    )
    completed = read_overview(ctx, request=query)

    def render() -> None:
        payload = completed.payload
        if not isinstance(payload, OverviewCalendarRead):
            raise ValueError("overview calendar projection has the wrong kind")
        if payload.calendar is not None:
            calendar = payload.calendar.to_calendar()
            if not calendar.taxpayer_model_declared or (calendar.warnings and not allow_incomplete):
                raise _incomplete_refusal(
                    completed,
                    payload.refusal_requirements,
                    undeclared=not calendar.taxpayer_model_declared,
                    warning_count=len(calendar.warnings)
                    if calendar.taxpayer_model_declared
                    else len(payload.refusal_requirements),
                )
            typed, lines, notices = overview_calendar_output(
                calendar,
                calendar.range,
                evidence_notices=tuple(_notice(row) for row in payload.notices),
                deemed_served_legal_ref=payload.deemed_served_legal_ref,
            )
        else:
            typed, lines, notices = _overview_calendar_survey_output(completed, payload, allow_incomplete)
        emit_envelope(ctx, command="overview.calendar", result=typed, lines=lines, notices=notices)

    _emit_read(completed, render)


def overview_agenda(
    ctx: typer.Context, as_of: str | None = None, horizon_days: int = 14, allow_incomplete: bool = False
) -> None:
    """Render canonical next-due cohorts captured in the worker."""
    if horizon_days <= 0:
        raise bad(tr("cli.overview.agenda.errors.invalid_horizon"))
    query = _request(
        OverviewReadKind.AGENDA,
        as_of=_parse_iso_date(as_of, label="--date") if as_of else today_madrid(),
        horizon_days=horizon_days,
        allow_incomplete=allow_incomplete,
    )
    completed = read_overview(ctx, request=query)

    def render() -> None:
        payload = completed.payload
        if not isinstance(payload, OverviewAgendaRead):
            raise ValueError("overview agenda projection has the wrong kind")
        agenda = payload.agenda.to_agenda()
        if (not agenda.taxpayer_model_declared or agenda.warnings) and not allow_incomplete:
            raise _incomplete_refusal(
                completed,
                payload.refusal_requirements,
                undeclared=not agenda.taxpayer_model_declared,
                warning_count=len(agenda.warnings)
                if agenda.taxpayer_model_declared
                else len(payload.refusal_requirements),
            )
        typed, lines, notices = overview_agenda_output(agenda)
        emit_envelope(ctx, command="overview.agenda", result=typed, lines=lines, notices=notices)

    _emit_read(completed, render)


def overview_backlog(
    ctx: typer.Context,
    from_date: str | None = None,
    to_date: str | None = None,
    allow_incomplete: bool = False,
) -> None:
    """Render canonical past-due rows captured in the worker."""
    fields: dict[str, object] = {"allow_incomplete": allow_incomplete}
    if from_date is not None:
        fields["from_date"] = _parse_iso_date(from_date, label="--from")
    if to_date is not None:
        fields["to_date"] = _parse_iso_date(to_date, label="--to")
    completed = read_overview(ctx, request=_request(OverviewReadKind.BACKLOG, **fields))

    def render() -> None:
        payload = completed.payload
        if not isinstance(payload, OverviewBacklogRead):
            raise ValueError("overview backlog projection has the wrong kind")
        backlog = payload.backlog.to_backlog()
        if not backlog.taxpayer_model_declared or (backlog.warnings and not allow_incomplete):
            raise _incomplete_refusal(
                completed,
                payload.refusal_requirements,
                undeclared=not backlog.taxpayer_model_declared,
                warning_count=len(backlog.warnings)
                if backlog.taxpayer_model_declared
                else len(payload.refusal_requirements),
            )
        notice = _notice(payload.notices[0]) if payload.notices else None
        typed, lines, notices = overview_backlog_output(backlog, work_units_notice=notice)
        emit_envelope(ctx, command="overview.backlog", result=typed, lines=lines, notices=notices)

    _emit_read(completed, render)


def overview_explain(ctx: typer.Context, modelo: str, year: int | None = None) -> None:
    """Render canonical applicability with its already-disclosed profile facts."""
    fields: dict[str, object] = {"modelo": modelo}
    if year is not None:
        fields["year"] = year
    completed = read_overview(ctx, request=_request(OverviewReadKind.EXPLAIN, **fields))

    def render() -> None:
        payload = completed.payload
        if not isinstance(payload, OverviewExplainRead):
            raise ValueError("overview explanation projection has the wrong kind")
        typed, lines = overview_explain_output(payload.explanation.to_explain())
        emit_envelope(
            ctx,
            command="overview.explain",
            result=typed,
            lines=lines,
            notices=tuple(_notice(row) for row in payload.notices),
        )

    _emit_read(completed, render)


def overview_prepare(ctx: typer.Context, modelo: str, year: int, period: str) -> None:
    """Render the canonical exact-period preparation checklist."""
    canonical = _canonical_period(period, year=year)
    completed = read_overview(
        ctx,
        request=_request(OverviewReadKind.PREPARE, modelo=modelo, period=PublicPeriod.from_period(canonical)),
    )

    def render() -> None:
        payload = completed.payload
        if not isinstance(payload, OverviewPrepareRead):
            raise ValueError("overview preparation projection has the wrong kind")
        typed, lines, notices = overview_prepare_output(payload.preparation.to_walkthrough())
        emit_envelope(ctx, command="overview.prepare", result=typed, lines=lines, notices=notices)

    _emit_read(completed, render)


def overview_pipeline(ctx: typer.Context, year: int, period: str) -> None:
    """Render one authenticated profile worker's pipeline-health snapshot."""
    from ._ledger_payloads import LedgerStatusResult

    canonical_period = _canonical_period(period, year=year)
    completed = read_overview_pipeline(
        ctx, period=canonical_period, output_language=OutputLanguage(current_output_language())
    )
    try:
        report = completed.report.to_report()
        typed_result, lines, notices = overview_pipeline_output(
            report, ledger=strict_round_trip(LedgerStatusResult, report.ledger)
        )
        emit_envelope(ctx, command="overview.pipeline", result=typed_result, lines=lines, notices=notices)
    except typer.Exit:
        raise
    except Exception:
        receipt = completed.completion
        raise submitted_operation_error(
            receipt.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=receipt.terminal_condition,
            effect=receipt.effect,
            refusal_code=receipt.refusal_code,
        ) from None


__all__ = [
    "overview_agenda",
    "overview_backlog",
    "overview_calendar",
    "overview_explain",
    "overview_pipeline",
    "overview_prepare",
    "overview_status",
]


def _overview_calendar_survey_output(
    completed: OverviewReadCompletion, payload: OverviewCalendarRead, allow_incomplete: bool
) -> tuple[OverviewCalendarResult, list[str], list[Notice]]:
    """Render locked and active profiles with the existing incomplete-calendar refusals."""
    survey = payload.survey
    if survey is None:
        raise ValueError("overview calendar survey is missing")
    lines = [
        f"from\t{survey.from_date.isoformat()}",
        f"to\t{survey.to_date.isoformat()}",
        f"profiles\t{int(survey.active_calendar is not None)}",
    ]
    for pointer in survey.locked:
        lines.extend(
            (
                f"profile\t{pointer.profile_id}\t{pointer.label}",
                f"profile_locked\t{pointer.profile_id}\t{pointer.label}",
            )
        )
    lines.extend(
        f"profile_setup_incomplete\t{pointer.profile_id}\t{pointer.label}" for pointer in survey.setup_incomplete
    )
    profiles: list[dict[str, object]] = []
    notices: list[Notice] = []
    if survey.active_calendar is not None and survey.active_profile_id and survey.active_label:
        calendar = survey.active_calendar.to_calendar()
        if calendar.warnings and not allow_incomplete:
            raise _incomplete_refusal(
                completed,
                payload.refusal_requirements,
                undeclared=False,
                warning_count=len(calendar.warnings),
            )
        profile, profile_lines, profile_notices = overview_calendar_profile_output(
            bucket_id=survey.active_profile_id,
            label=survey.active_label,
            cal=calendar,
            deemed_served_legal_ref=payload.deemed_served_legal_ref,
        )
        profiles.append(profile)
        lines.extend(profile_lines)
        notices.extend(profile_notices)
    typed = OverviewCalendarResult.model_validate({"profiles": profiles})
    return typed, lines, notices
