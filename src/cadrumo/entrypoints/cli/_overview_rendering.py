"""Text rendering and notice projection for ``overview status``.

This module consumes an application-built
:class:`OverviewStatusReport` and turns it into
localized text lines plus :class:`Notice` objects for the
:class:`SchemaEnvelope` notice channel.  It is
presentation-only: active-profile discovery, storage reads, and status assembly
stay upstream in the application overview layer and :mod:`._overview`.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...application.overview import (
    CoverageAdviceReason,
    ModeloReadinessState,
    ObligationCoverageReport,
    OverviewCalendar,
    OverviewCalendarEvent,
    OverviewCalendarRange,
    OverviewStatusReport,
    actionable_post_filing_events,
)
from ...application.overview import (
    DataPrepStepState as _DataPrepStepState,
)
from ...core import Modelo
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._overview_payloads import (
    OverviewAgendaResult,
    OverviewBacklogResult,
    OverviewCalendarResult,
    OverviewExplainResult,
    OverviewPipelineModeloPayload,
    OverviewPipelineResult,
    OverviewPrepareResult,
    OverviewPrepareStepPayload,
)


def overview_next_step_notices(report: OverviewStatusReport) -> list[Notice]:
    """Surface the workspace-state next-step guidance as :class:`Notice` values.

    Mirrors the text-mode ``_next_step_lines`` guidance so JSON consumers
    receive the same forward guidance the text surface already shows,
    through the uniform envelope ``notices`` channel rather than a bespoke
    payload field. Info severity keeps the envelope ``status`` at
    ``success``.
    """
    return [
        Notice(severity=NoticeSeverity.INFO, code="overview.status.next_step", message=line.strip())
        for line in _next_step_lines(report)
        if line.strip()
    ]


_COVERAGE_NOTICE_CODE = "overview.coverage.incomplete"


def overview_coverage_notices(coverage: ObligationCoverageReport) -> list[Notice]:
    """Project the obligation-coverage advisory onto the envelope notice channel.

    Returns a single default-visible :class:`Notice`
    naming every registry modelo the surface could not positively scope — the
    ``advised`` bucket of the reconciliation — so an operator (or the autonomous
    agent the CLI targets) is never allowed to trust ``overview`` and silently
    under-file. Severity is ``warning`` when at least one advised obligation is
    positively known to apply but has no deadline window (the Modelo-190 shape —
    an unambiguous under-filing risk); otherwise ``info`` for the merely
    applicability-undetermined set. The advised modelo→reason map rides on
    :attr:`Notice.context` so machine consumers keep the
    structured list. Empty ``advised`` yields no notice.
    """
    if not coverage.has_advisories:
        return []
    advised = coverage.advised
    modelos = ", ".join(item.modelo for item in advised)
    window_missing = any(item.reason is CoverageAdviceReason.APPLICABLE_WINDOW_MISSING for item in advised)
    severity = NoticeSeverity.WARNING if window_missing else NoticeSeverity.INFO
    message = tr(
        "cli.overview.coverage.investigate",
        default=(
            "%{count} filing obligation(s) could not be positively scoped for "
            "this profile and may be under-reported: %{modelos}. Investigate "
            "each with 'aeat app overview explain <modelo>'."
        ),
        count=len(advised),
        modelos=modelos,
    )
    return [
        Notice(
            severity=severity,
            code=_COVERAGE_NOTICE_CODE,
            message=message,
            suggestion=f"aeat app overview explain {advised[0].modelo}",
            context={item.modelo: item.reason.value for item in advised},
        ),
    ]


_POST_FILING_NOTICE_CODE = "overview.post_filing.pending"


def overview_post_filing_event_notices(events: Sequence[OverviewCalendarEvent]) -> list[Notice]:
    """Surface pulled AEAT post-filing events that demand operator attention.

    Filters the observed calendar events to the actionable
    :class:`PostFilingEventKind` categories through
    :func:`actionable_post_filing_events` — a
    requerimiento, a propuesta / acuerdo de liquidación, a procedimiento
    sancionador, or a recaudación enforcement act — and projects them onto a
    single ``warning``-severity :class:`Notice` so the
    overview never silently buries a pending requerimiento in an
    undifferentiated event list. The per-event reference→kind map rides on
    :attr:`Notice.context` so machine consumers keep the
    structured list. Empty when no actionable event is present.
    """
    actionable = actionable_post_filing_events(tuple(events))
    if not actionable:
        return []
    kinds = sorted({event.post_filing_kind.value for event in actionable if event.post_filing_kind is not None})
    message = tr(
        "cli.overview.post_filing.pending",
        default=(
            "%{count} AEAT post-filing event(s) require attention: %{kinds}. "
            "Review them with 'aeat app live notifications list'."
        ),
        count=len(actionable),
        kinds=", ".join(kinds),
    )
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=_POST_FILING_NOTICE_CODE,
            message=message,
            suggestion="aeat app live notifications list",
            context={
                event.reference_id: event.post_filing_kind.value
                for event in actionable
                if event.post_filing_kind is not None
            },
        ),
    ]


def overview_calendar_output(
    cal: OverviewCalendar,
    rng: OverviewCalendarRange,
    *,
    evidence_notices: Sequence[Notice],
) -> tuple[OverviewCalendarResult, list[str], list[Notice]]:
    """Project one active-profile calendar into payload, text lines, and notices."""
    typed_cal = OverviewCalendarResult.model_validate(cal.model_dump(mode="json"))
    lines: list[str] = [
        f"from\t{rng.from_date.isoformat()}",
        f"to\t{rng.to_date.isoformat()}",
        f"entries\t{len(cal.entries)}",
        f"events\t{len(cal.events)}",
    ]
    for entry in cal.entries:
        lines.append(
            f"{entry.modelo}\t{entry.period}\t{entry.user_state.value}"
            f"\topens={entry.opens_on.isoformat()}"
            f"\tcloses={entry.closes_on.isoformat()}"
            f"\tadjusted={entry.adjusted_closes_on.isoformat()}"
            f"\tshift={_calendar_shift_reason_text(entry.shift_reason)}"
            f"\tcenso_enrolment={entry.censo_enrolment_state.value}"
            f"\t{_calendar_filing_evidence_text_fields(entry.filing_evidence)}"
            f"\t{_calendar_entry_work_unit_text_fields(entry)}",
        )
    for warning in cal.warnings:
        lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
    for event in cal.events:
        lines.append(_calendar_event_text_line(event))
    if cal.completeness.computable_modelos:
        lines.append(
            f"computable\t{len(cal.completeness.computable_modelos)}"
            f"\tdefaulted\t{len(cal.completeness.defaulted_modelos)}",
        )
    for suppressed in cal.suppressed_entries:
        lines.append(
            f"suppressed\t{suppressed.modelo}\t{suppressed.period}"
            f"\tverdict={suppressed.verdict.value}"
            f"\treason={suppressed.reason[:80]}",
        )
    coverage_notices = overview_coverage_notices(cal.coverage)
    for notice in coverage_notices:
        lines.append(f"coverage_advised\t{len(cal.coverage.advised)}\t{notice.message}")
    post_filing_notices = overview_post_filing_event_notices(cal.events)
    for notice in post_filing_notices:
        lines.append(f"post_filing_pending\t{len(notice.context or {})}\t{notice.message}")
    calendar_notices = [*coverage_notices, *post_filing_notices]
    for notice in evidence_notices:
        lines.append(f"{notice.code}\t{notice.message}")
        calendar_notices.append(notice)
    return typed_cal, lines, calendar_notices


def overview_calendar_profile_output(
    *,
    bucket_id: str,
    label: str,
    cal: OverviewCalendar,
) -> tuple[dict[str, object], list[str], list[Notice]]:
    """Project one profile block for ``overview calendar --all-profiles``."""
    lines = [
        f"profile\t{bucket_id}\t{label}",
        f"entries\t{len(cal.entries)}",
        f"events\t{len(cal.events)}",
    ]
    for entry in cal.entries:
        lines.append(
            f"{entry.modelo}\t{entry.period}\t{entry.user_state.value}"
            f"\topens={entry.opens_on.isoformat()}"
            f"\tcloses={entry.closes_on.isoformat()}"
            f"\tadjusted={entry.adjusted_closes_on.isoformat()}"
            f"\tshift={_calendar_shift_reason_text(entry.shift_reason)}"
            f"\tcenso_enrolment={entry.censo_enrolment_state.value}"
            f"\t{_calendar_filing_evidence_text_fields(entry.filing_evidence)}"
            f"\t{_calendar_entry_work_unit_text_fields(entry)}",
        )
    if not cal.taxpayer_model_declared:
        lines.append(
            f"warning\tINCOMPLETE_TAXPAYER_MODEL\t"
            f"{cal.incomplete_reason or tr('cli.overview.taxpayer_model_undeclared')}",
        )
    for warning in cal.warnings:
        lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
    for event in cal.events:
        lines.append(_calendar_event_text_line(event))
    for suppressed in cal.suppressed_entries:
        lines.append(
            f"suppressed\t{suppressed.modelo}\t{suppressed.period}"
            f"\tverdict={suppressed.verdict.value}"
            f"\treason={suppressed.reason[:80]}",
        )
    notices: list[Notice] = []
    for notice in overview_coverage_notices(cal.coverage):
        tagged = notice.model_copy(update={"context": {**(notice.context or {}), "profile": label}})
        notices.append(tagged)
        lines.append(f"coverage_advised\t{label}\t{len(cal.coverage.advised)}\t{notice.message}")
    for notice in overview_post_filing_event_notices(cal.events):
        tagged = notice.model_copy(update={"context": {**(notice.context or {}), "profile": label}})
        notices.append(tagged)
        lines.append(f"post_filing_pending\t{label}\t{len(notice.context or {})}\t{notice.message}")
    payload = {
        "profile_id": bucket_id,
        "label": label,
        "calendar": cal.model_dump(mode="json"),
    }
    return payload, lines, notices


def overview_agenda_output(agenda) -> tuple[OverviewAgendaResult, list[str], list[Notice]]:
    """Project an overview agenda into payload, text lines, and notices."""
    typed_agenda = OverviewAgendaResult.model_validate(agenda.model_dump(mode="json"))
    lines: list[str] = [
        f"as_of\t{agenda.as_of.isoformat()}",
        f"horizon_days\t{agenda.horizon_days}",
    ]
    if agenda.next_due is not None:
        lines.append(
            f"next_due\t{agenda.next_due.modelo}\t{agenda.next_due.period}"
            f"\tcloses={agenda.next_due.adjusted_closes_on.isoformat()}",
        )
    else:
        lines.append("next_due\t(none)")
    lines.append(f"due_today\t{len(agenda.due_today)}")
    for entry in agenda.due_today:
        lines.append(f"  {entry.modelo}\t{entry.period}\t{entry.adjusted_closes_on.isoformat()}")
    lines.append(f"due_soon\t{len(agenda.due_soon)}")
    for entry in agenda.due_soon:
        lines.append(f"  {entry.modelo}\t{entry.period}\t{entry.adjusted_closes_on.isoformat()}")
    lines.append(f"overdue\t{len(agenda.overdue)}")
    for entry in agenda.overdue:
        lines.append(f"  {entry.modelo}\t{entry.period}\t{entry.adjusted_closes_on.isoformat()}")
    for warning in agenda.warnings:
        lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
    coverage_notices = overview_coverage_notices(agenda.coverage)
    for notice in coverage_notices:
        lines.append(f"coverage_advised\t{len(agenda.coverage.advised)}\t{notice.message}")
    return typed_agenda, lines, coverage_notices


def overview_backlog_output(
    backlog,
    *,
    work_units_notice: Notice | None,
) -> tuple[OverviewBacklogResult, list[str], list[Notice]]:
    """Project an overview backlog into payload, text lines, and notices."""
    typed_backlog = OverviewBacklogResult.model_validate(backlog.model_dump(mode="json"))
    lines: list[str] = [
        f"from\t{backlog.range.from_date.isoformat()}",
        f"to\t{backlog.range.to_date.isoformat()}",
        f"as_of\t{backlog.as_of.isoformat()}",
        f"late_count\t{backlog.late_count}",
    ]
    for entry in backlog.items:
        lines.append(
            f"{entry.modelo}\t{entry.period}\tcloses={entry.adjusted_closes_on.isoformat()}"
            f"\t{_calendar_entry_work_unit_text_fields(entry)}",
        )
    for warning in backlog.warnings:
        lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
    coverage_notices = overview_coverage_notices(backlog.coverage)
    for notice in coverage_notices:
        lines.append(f"coverage_advised\t{len(backlog.coverage.advised)}\t{notice.message}")
    backlog_notices = [*coverage_notices]
    if work_units_notice is not None:
        lines.append(f"work_units_degraded\t{work_units_notice.message}")
        backlog_notices.append(work_units_notice)
    return typed_backlog, lines, backlog_notices


def overview_explain_output(result) -> tuple[OverviewExplainResult, list[str]]:
    """Project an overview applicability explanation into payload and text lines."""
    typed_explain = OverviewExplainResult.model_validate(result.model_dump(mode="json"))
    lines: list[str] = [
        f"modelo\t{result.modelo}",
        f"year\t{result.year}",
        f"applicable\t{str(result.applicable).lower()}",
        f"verdict\t{result.verdict.value}",
        f"rationale\t{result.rationale}",
        f"legal_refs\t{', '.join(result.legal_refs)}",
    ]
    if result.scheduling_rationale is not None:
        lines.append(f"scheduling_rationale\t{result.scheduling_rationale}")
    if result.out_of_plazo_warning is not None:
        lines.append(f"warning\tout_of_plazo\t{result.out_of_plazo_warning}")
    for fact_name, fact_value in sorted(result.profile_facts.items()):
        lines.append(f"profile_fact\t{fact_name}\t{fact_value}")
    return typed_explain, lines


def overview_prepare_output(walkthrough) -> tuple[OverviewPrepareResult, list[str], list[Notice]]:
    """Project a data-prep walkthrough into payload, text lines, and notices."""
    typed_result = OverviewPrepareResult(
        modelo=walkthrough.modelo,
        filing_year=walkthrough.filing_year,
        period=walkthrough.period,
        steps=[
            OverviewPrepareStepPayload(
                step_id=step.step_id,
                state=step.state,
                summary=step.summary,
                next_command=step.next_command,
            )
            for step in walkthrough.steps
        ],
        ready_for_calculation=walkthrough.ready_for_calculation,
    )
    lines: list[str] = [
        f"modelo\t{walkthrough.modelo}",
        f"period\t{walkthrough.period} {walkthrough.filing_year}",
        f"ready_for_calculation\t{str(walkthrough.ready_for_calculation).lower()}",
        "",
    ]
    notices: list[Notice] = []
    for index, step in enumerate(walkthrough.steps, start=1):
        lines.append(f"{index}. [{step.state.value}] {step.summary}")
        lines.append(f"   next: {step.next_command}")
        if step.state is not _DataPrepStepState.DONE:
            notices.append(
                Notice(
                    severity=NoticeSeverity.INFO,
                    code=f"overview.prepare.next_step.{step.step_id.value}",
                    message=step.summary,
                    suggestion=step.next_command,
                    context={"state": step.state.value},
                ),
            )
    return typed_result, lines, notices


def overview_pipeline_output(report, *, ledger) -> tuple[OverviewPipelineResult, list[str], list[Notice]]:
    """Project a pipeline-health report into payload, text lines, and notices."""
    typed_result = OverviewPipelineResult(
        filing_year=report.filing_year,
        period=report.period,
        ledger=ledger,
        modelos=[
            OverviewPipelineModeloPayload(
                modelo=row.modelo,
                work_unit_id=row.work_unit_id,
                state=row.state,
                blocking_finding_count=row.blocking_finding_count,
                warning_finding_count=row.warning_finding_count,
                summary=row.summary,
                next_command=row.next_command,
            )
            for row in report.modelos
        ],
        total_blocking_findings=report.total_blocking_findings,
        total_warning_findings=report.total_warning_findings,
        ready=report.ready,
    )
    lines: list[str] = [
        f"{tr('cli.overview.labels.period', default='Period')}\t{report.period} {report.filing_year}",
        f"{tr('cli.overview.pipeline.labels.ready', default='ready')}\t{str(report.ready).lower()}",
        "",
        tr("cli.overview.pipeline.labels.ledger_section", default="Ledger:"),
        f"  {tr('cli.ledger.labels.rows')}\t{report.ledger.total_count}",
        f"  {tr('cli.ledger.labels.pending')}\t{report.ledger.pending_review_count}",
        f"  {tr('cli.ledger.labels.reviewed')}\t{report.ledger.reviewed_count}",
        f"  {tr('cli.ledger.labels.skipped')}\t{report.ledger.skipped_count}",
        f"  {tr('cli.ledger.labels.readiness_issues')}\t{report.ledger.readiness_issue_count}",
        "",
        tr("cli.overview.pipeline.labels.modelos_section", default="Modelos:"),
    ]
    notices: list[Notice] = []
    if not report.modelos:
        no_units_message = tr(
            "cli.overview.pipeline.no_work_units",
            default="No modelo work units for this period yet.",
        )
        lines.append(f"  {no_units_message}")
    for row in report.modelos:
        lines.append(f"  [{row.state.value}] Modelo {row.modelo}: {row.summary}")
        lines.append(f"    next: {row.next_command}")
        if row.state is not ModeloReadinessState.FILED:
            severity = NoticeSeverity.WARNING if row.state is ModeloReadinessState.BLOCKED else NoticeSeverity.INFO
            notices.append(
                Notice(
                    severity=severity,
                    code=f"overview.pipeline.modelo.{row.state.value}",
                    message=row.summary,
                    suggestion=row.next_command,
                    context={"modelo": row.modelo, "state": row.state.value},
                ),
            )
    lines.append("")
    lines.append(
        f"{tr('cli.overview.pipeline.labels.findings_section', default='Findings:')} "
        f"{report.total_blocking_findings} blocking, {report.total_warning_findings} warning",
    )
    return typed_result, lines, notices


def render_cli_overview_status_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Render :class:`OverviewStatusReport` as operator-facing CLI text.

    The renderer preserves the same next-step decisions used by
    :func:`overview_next_step_notices`,
    so text and JSON-envelope notice output stay aligned.
    """
    lines: list[str] = [
        tr("cli.overview.status.title"),
        "",
        _profile_line(report),
        _transactions_line(report),
        _invoices_line(report),
        _drafts_line(report),
        _work_units_line(report),
        *_storage_lines(report),
        *_filing_obligation_lines(report),
        "",
        tr("cli.overview.status.next_heading"),
        *_next_step_lines(report),
    ]
    return tuple(lines)


def _next_step_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Return next-step guidance that reflects the actual workspace state.

    A workspace with ledger data already recorded must not be told to
    "import a bank statement" — that step is done. The guidance walks
    the operator forward: import when the ledger is empty, classify /
    work-modelo when transactions exist, continue the modelo flow when
    work units are already in progress. Unsupported
    :class:`Modelo` work-unit creation is diverted to discovery
    guidance instead of a dead command.
    """
    if report.work_units > 0:
        return (
            tr(
                "cli.overview.status.next_work_calculate_command",
                default="  aeat app modelo work list - resume an in-progress modelo work unit.",
            ),
            _modelo_work_create_guidance_line(report),
            tr("cli.overview.status.next_landing_command"),
        )
    if report.transactions > 0 or report.invoices > 0:
        return (
            tr(
                "cli.overview.status.next_review_command",
            ),
            _modelo_work_from_ledger_guidance_line(report),
            tr("cli.overview.status.next_landing_command"),
        )
    return (
        tr("cli.overview.status.next_import_command"),
        tr("cli.overview.status.next_review_command"),
        tr("cli.overview.status.next_landing_command"),
    )


def _modelo_210_unsupported_guidance_line(report: OverviewStatusReport) -> str | None:
    if Modelo.M210.value in report.unsupported_work_create_modelos:
        return tr(
            "cli.overview.status.next_modelo_210_unsupported_command",
            default=(
                "  aeat app modelo describe 210 - Modelo 210 is visible for IRNR discovery, "
                "but local work-unit creation is not supported yet; file through AEAT Sede G320."
            ),
        )
    return None


def _modelo_work_create_guidance_line(report: OverviewStatusReport) -> str:
    return _modelo_210_unsupported_guidance_line(report) or tr(
        "cli.overview.status.next_work_create_command",
        default="  aeat app modelo work create - start a work unit for another modelo.",
    )


def _modelo_work_from_ledger_guidance_line(report: OverviewStatusReport) -> str:
    return _modelo_210_unsupported_guidance_line(report) or tr(
        "cli.overview.status.next_modelo_work_command",
        default="  aeat app modelo work create - start a modelo declaration from your ledger data.",
    )


def _work_units_line(report: OverviewStatusReport) -> str:
    if report.work_units == 0 and report.discarded_work_units == 0:
        return tr(
            "cli.overview.status.work_units_empty",
            default="No modelo work units have been started yet.",
        )
    if report.discarded_work_units > 0:
        # The bare total misleads when some units are discarded: the
        # operator reads "5 work units" and counts abandoned ones as
        # live work. The line states the active / discarded split.
        return tr(
            "cli.overview.status.work_units_present_with_discarded",
            default=(
                "%{count} active modelo work unit(s) (%{discarded} discarded) "
                "in this local storage - your active modelo work is saved; "
                "resume it with `aeat app modelo work list`."
            ),
            count=report.work_units,
            discarded=report.discarded_work_units,
        )
    return tr(
        "cli.overview.status.work_units_present",
        default=(
            "%{count} modelo work unit(s) are in progress in this local storage "
            "- your modelo work is saved; resume it with `aeat app modelo work list`."
        ),
        count=report.work_units,
    )


def _profile_line(report: OverviewStatusReport) -> str:
    if report.active_profile is None:
        return tr("cli.overview.status.profile_missing")
    # The prose line names the operator-chosen display name only; the
    # immutable bucket UUID is structured-payload noise in prose and is
    # carried solely on the JSON / secondary `profile_id` field. Fall
    # back to the UUID alone when the manifest carried no display name.
    name = report.active_profile_name
    if name:
        return tr("cli.overview.status.profile_active", profile=name)
    return tr("cli.overview.status.profile_active", profile=report.active_profile)


def _transactions_line(report: OverviewStatusReport) -> str:
    if report.transactions == 0:
        return tr("cli.overview.status.transactions_empty")
    return tr("cli.overview.status.transactions_present", count=report.transactions)


def _invoices_line(report: OverviewStatusReport) -> str:
    if report.invoices == 0:
        return tr("cli.overview.status.invoices_empty")
    return tr("cli.overview.status.invoices_present", count=report.invoices)


def _drafts_line(report: OverviewStatusReport) -> str:
    if report.drafts == 0:
        # Two independent operators read the bare "no saved declaration
        # drafts" line - which sits next to the work-units line - as
        # "your work is gone". When work units exist, the line must say
        # so explicitly: declaration drafts and modelo work units are
        # separate stores, and an empty draft store never means lost
        # modelo work.
        if report.work_units > 0:
            return tr(
                "cli.overview.status.drafts_empty_with_work_units",
                default=(
                    "No declaration drafts are saved - this is normal and does not affect your modelo work units below."
                ),
            )
        return tr("cli.overview.status.drafts_empty")
    return tr("cli.overview.status.drafts_present", count=report.drafts)


def _storage_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    if report.unreadable_rows == 0:
        return (tr("cli.overview.status.storage_ok"),)
    return (
        tr("cli.overview.status.storage_warning", count=report.unreadable_rows),
        tr("cli.overview.status.integrity_next"),
    )


def _filing_obligation_lines(report: OverviewStatusReport) -> tuple[str, ...]:
    """Return localized filing-obligation advisory lines from the report."""
    if not report.filing_obligation_advisories:
        return ()
    lines: list[str] = [""]
    for key in report.filing_obligation_advisories:
        lines.append(tr(key))
    return tuple(lines)


def _calendar_filing_evidence_text_fields(filing_evidence) -> str:
    """Return stable text metrics for one calendar row's filing evidence."""
    fields = [
        f"local={filing_evidence.local_filing_state.value}",
        f"aeat={filing_evidence.aeat_submission_state.value}",
        f"justificante={str(filing_evidence.justificante_verified).lower()}",
    ]
    if filing_evidence.local_filing_record_id:
        fields.append(f"local_record={filing_evidence.local_filing_record_id}")
    if filing_evidence.aeat_reference_id:
        fields.append(f"aeat_ref={filing_evidence.aeat_reference_id}")
    if filing_evidence.aeat_submitted_at:
        fields.append(f"aeat_submitted_at={filing_evidence.aeat_submitted_at.isoformat()}")
    if filing_evidence.aeat_evidence_kind:
        fields.append(f"aeat_kind={filing_evidence.aeat_evidence_kind}")
    if filing_evidence.aeat_evidence_conflict_reference_ids:
        fields.append("aeat_conflict_refs=" + ",".join(filing_evidence.aeat_evidence_conflict_reference_ids))
    if filing_evidence.verified_justificante_csv:
        fields.append(f"verified_justificante_csv={filing_evidence.verified_justificante_csv}")
    if filing_evidence.evidence_source:
        fields.append(f"evidence_source={filing_evidence.evidence_source}")
    return "\t".join(fields)


def _calendar_entry_work_unit_text_fields(entry) -> str:
    fields = [f"source={entry.source.value}"]
    if entry.local_work_unit_id:
        fields.append(f"work_unit={entry.local_work_unit_id}")
    if entry.local_work_unit_name:
        fields.append(f"work_name={entry.local_work_unit_name}")
    if entry.local_work_unit_revision_id:
        fields.append(f"work_revision={entry.local_work_unit_revision_id}")
    return "\t".join(fields)


def _calendar_shift_reason_part_text(part: str) -> str:
    """Return the localized text label for one shift-reason token."""
    if part == "business_day":
        return tr("cli.overview.calendar.shift.business_day", default="Business day")
    if part == "calendar_unavailable":
        return tr("cli.overview.calendar.shift.calendar_unavailable", default="Calendar unavailable")
    if part == "domingo":
        return tr("cli.overview.calendar.shift.domingo", default="Sunday")
    if part == "modelo_exception":
        return tr("cli.overview.calendar.shift.modelo_exception", default="Modelo exception")
    if part == "sabado":
        return tr("cli.overview.calendar.shift.sabado", default="Saturday")
    return part


def _calendar_shift_reason_text(shift_reason: str) -> str:
    """Return the localized operator label for a calendar shift reason."""
    return " + ".join(_calendar_shift_reason_part_text(part) for part in shift_reason.split(" + "))


def _calendar_event_text_line(event: OverviewCalendarEvent) -> str:
    """Return the stable text line for one calendar event."""
    parts = [
        "event",
        event.event_type.value,
        event.event_date.isoformat(),
        event.source,
        event.reference_id,
        event.summary,
    ]
    if event.post_filing_kind is not None:
        parts.append(f"kind={event.post_filing_kind.value}")
    if event.modelo:
        parts.append(f"modelo={event.modelo}")
    if event.filing_year is not None:
        parts.append(f"year={event.filing_year}")
    if event.period:
        parts.append(f"period={event.period}")
    if event.status:
        parts.append(f"status={event.status}")
    if event.aeat_submission_state:
        parts.append(f"aeat={event.aeat_submission_state.value}")
    if event.aeat_submitted_at:
        parts.append(f"aeat_submitted_at={event.aeat_submitted_at.isoformat()}")
    if event.justificante_verified is not None:
        parts.append(f"justificante={str(event.justificante_verified).lower()}")
    if event.verified_justificante_csv:
        parts.append(f"verified_justificante_csv={event.verified_justificante_csv}")
    return "\t".join(parts)


__all__ = [
    "overview_agenda_output",
    "overview_backlog_output",
    "overview_calendar_output",
    "overview_calendar_profile_output",
    "overview_coverage_notices",
    "overview_explain_output",
    "overview_pipeline_output",
    "overview_post_filing_event_notices",
    "overview_prepare_output",
    "render_cli_overview_status_lines",
]
