"""Text rendering and notice projection for the ``overview`` command family.

This module consumes application-built overview read models and turns them into
localized text lines plus :class:`Notice` objects for the
:class:`SchemaEnvelope` notice channel.  It is presentation-only: active-profile
discovery, storage reads, and status assembly stay upstream in the application
overview layer and :mod:`._overview`.

Forward guidance has exactly ONE projection here.  A producer declares a
catalogue action; :func:`resolve_notice_action` resolves it once against the
live command tree; the resulting
:class:`~core.json_contract.ResolvedNoticeAction` is then the single object
carried by the payload row, by the envelope notice, and - through
:func:`~._common._action_text_lines` - by the executable text line.  Text and
JSON therefore cannot state different advice, because there is only one thing
to state.

Guidance used to be an ``aeat ...`` sentence stored in four locale catalogues:
the text surface printed the sentence, and the JSON surface recovered a message
from it by splitting on ``" - "``.  Two renderers, one string, and a verb rename
broke both silently.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from ...application.operator_actions import ActionReference, DeclaredNextAction
from ...application.overview import (
    NO_AEAT_HISTORY_NOTICE_CODE,
    CalendarWarning,
    CoverageAdviceReason,
    ModeloReadinessState,
    ObligationCoverageReport,
    OverviewCalendar,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarRange,
    OverviewStatusNextStep,
    OverviewStatusNextStepId,
    OverviewStatusReport,
    SuppressedCalendarEntry,
    actionable_post_filing_events,
    build_overview_status_next_steps,
)
from ...application.overview import (
    DataPrepStepState as _DataPrepStepState,
)
from ...core import (
    ActionArgumentSource,
    ActionArgumentStatus,
    NotificacionEstadoServicio,
)
from ...core.i18n import tr
from ...core.json_contract import (
    Notice,
    NoticeSeverity,
    ResolvedActionArgument,
    ResolvedNoticeAction,
    strict_round_trip,
)
from ._common import resolve_notice_action
from ._overview_payloads import (
    OverviewAgendaResult,
    OverviewBacklogResult,
    OverviewCalendarEntryPayload,
    OverviewCalendarEventPayload,
    OverviewCalendarResult,
    OverviewExplainResult,
    OverviewPipelineModeloPayload,
    OverviewPipelineResult,
    OverviewPrepareResult,
    OverviewPrepareStepPayload,
    OverviewRecargoBandPayload,
    OverviewRecoveryPayload,
)

_NEXT_STEP_NOTICE_CODE = "overview.status.next_step"


def _next_step_message(step_id: OverviewStatusNextStepId) -> str:
    """Return the localized explanation for one forward-guidance row.

    Each key is spelled as a literal argument to :func:`tr` so the locale
    scanner can see it; a key held only in a lookup table is invisible to the
    catalogue-parity gate and rots unnoticed.

    The prose explains, and only explains.  The executable half of the row is
    the resolved action, so a renamed verb can never leave a stale instruction
    stranded in four translated catalogues.
    """
    if step_id is OverviewStatusNextStepId.CREATE_PROFILE:
        return tr("cli.overview.status.next_step.create_profile")
    if step_id is OverviewStatusNextStepId.RESUME_WORK_UNIT:
        return tr("cli.overview.status.next_step.resume_work_unit")
    if step_id is OverviewStatusNextStepId.START_ANOTHER_WORK_UNIT:
        return tr("cli.overview.status.next_step.start_another_work_unit")
    if step_id is OverviewStatusNextStepId.START_WORK_UNIT_FROM_LEDGER:
        return tr("cli.overview.status.next_step.start_work_unit_from_ledger")
    if step_id is OverviewStatusNextStepId.MODELO_210_SEDE_ONLY:
        return tr("cli.overview.status.next_step.modelo_210_sede_only")
    if step_id is OverviewStatusNextStepId.REVIEW_LEDGER:
        return tr("cli.overview.status.next_step.review_ledger")
    if step_id is OverviewStatusNextStepId.IMPORT_TRANSACTIONS:
        return tr("cli.overview.status.next_step.import_transactions")
    if step_id is OverviewStatusNextStepId.REPAIR_STORAGE:
        return tr("cli.overview.status.next_step.repair_storage")
    return tr("cli.overview.status.next_step.command_guide")


def _next_step_notice(step: OverviewStatusNextStep) -> Notice:
    """Project one declared guidance row onto the envelope notice channel.

    The message carries the localized explanation and the action carries the
    executable identity.  Nothing here reads or rebuilds the other, so the two
    halves cannot disagree.
    """
    return Notice(
        severity=NoticeSeverity.INFO,
        code=_NEXT_STEP_NOTICE_CODE,
        message=_next_step_message(step.step_id),
        action=_resolved_action(step.next_action),
        context={"step": step.step_id.value},
    )


def _resolved_action(declaration: DeclaredNextAction | None) -> ResolvedNoticeAction | None:
    """Resolve one producer declaration against the live command surface.

    Returns ``None`` for a row that declared no continuation, which is how a
    producer states that the next move needs input it cannot supply.
    """
    if declaration is None:
        return None
    return resolve_notice_action(
        action=declaration.action,
        argument_bindings=tuple(
            ResolvedActionArgument.model_validate(binding.model_dump()) for binding in declaration.argument_bindings
        ),
    )


def _recovery_payload(entry: OverviewCalendarEntry) -> OverviewRecoveryPayload | None:
    """Resolve an overdue recovery's application declaration for CLI output."""
    if entry.recovery is None:
        return None
    next_action = _resolved_action(entry.recovery_action)
    if next_action is None:
        raise ValueError("overdue overview recovery requires an application action declaration")
    recargo_band = OverviewRecargoBandPayload.model_validate_json(entry.recovery.recargo_band.model_dump_json())
    return OverviewRecoveryPayload(
        still_filable=entry.recovery.still_filable,
        recargo_band=recargo_band,
        next_action=next_action,
    )


def overview_calendar_warning_notices(warnings: Sequence[CalendarWarning]) -> list[Notice]:
    """Project profile-completeness and evidence warnings onto the notice channel.

    A calendar warning always names a remedy, and that remedy is now the one
    resolved action every surface shares.  The text line beside it states only
    the localized explanation, because the executable form is rendered from
    this notice by the shared envelope rather than formatted a second time
    here.

    Severity is ``warning``: each of these rows means an obligation projection
    ran on a defaulted or unproven fact, which is exactly the case an operator
    must not scroll past.

    Args:
        warnings: The application-built warning rows for one query.

    Returns:
        One notice per warning, in the order the builder produced them.
    """
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=warning.code,
            message=tr(warning.message),
            action=_resolved_action(warning.fix_action),
            context={"affected_modelos": ",".join(warning.affected_modelos)} if warning.affected_modelos else None,
        )
        for warning in warnings
    ]


_COVERAGE_NOTICE_CODE = "overview.coverage.incomplete"


def overview_coverage_notices(coverage: ObligationCoverageReport) -> list[Notice]:
    """Project the obligation-coverage advisory onto the envelope notice channel.

    Returns one :class:`Notice` for every registry modelo the surface could not
    positively scope — the ``advised`` bucket of the reconciliation — so every
    executable explanation action has one concrete ``modelo`` argument.
    Severity is ``warning`` when at least one advised obligation is positively
    known to apply but has no deadline window (the Modelo-190 shape — an
    unambiguous under-filing risk); otherwise ``info`` for the merely
    applicability-undetermined set. Empty ``advised`` yields no notice.
    """
    if not coverage.has_advisories:
        return []
    advised = coverage.advised
    window_missing = any(item.reason is CoverageAdviceReason.APPLICABLE_WINDOW_MISSING for item in advised)
    severity = NoticeSeverity.WARNING if window_missing else NoticeSeverity.INFO
    return [
        Notice(
            severity=severity,
            code=_COVERAGE_NOTICE_CODE,
            message=tr(
                "cli.overview.coverage.investigate",
                default=(
                    "The filing obligation %{modelo} could not be positively scoped for this "
                    "profile and may be under-reported. Review its filing explanation."
                ),
                modelo=item.modelo,
            ),
            action=resolve_notice_action(
                action=ActionReference(action_id="operator.overview.explain"),
                argument_bindings=(
                    ResolvedActionArgument(
                        argument_name="modelo",
                        status=ActionArgumentStatus.RESOLVED,
                        value=item.modelo,
                        source=ActionArgumentSource.VERDICT_CONTEXT,
                        source_key="modelo",
                    ),
                ),
            ),
            context={"modelo": item.modelo, "reason": item.reason.value},
        )
        for item in advised
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
        "cli.overview.post_filing.pending_summary",
        default=("%{count} AEAT post-filing event(s) require attention: %{kinds}. Review the affected notifications."),
        count=len(actionable),
        kinds=", ".join(kinds),
    )
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=_POST_FILING_NOTICE_CODE,
            message=message,
            action=resolve_notice_action(action=ActionReference(action_id="operator.live.notifications.list")),
            context={
                event.reference_id: event.post_filing_kind.value
                for event in actionable
                if event.post_filing_kind is not None
            },
        ),
    ]


_DEEMED_SERVED_NOTICE_CODE = "overview.notificacion.rechazo_tacito"

#: Legal-catalogue entry establishing the rechazo-tácito window the notice reports.
#: It rides on :attr:`Notice.context` so the operator can trace the claim that a
#: notification nobody opened is nevertheless legally served back to the provision
#: that says so, rather than taking the surface's word for it.
DEEMED_SERVED_LEGAL_REF = "ley-39-2015:art-43.2"


def overview_deemed_served_notification_notices(events: Sequence[OverviewCalendarEvent]) -> list[Notice]:
    """Surface notifications the law already deems served, whatever their procedural kind.

    A DEHu notification left unopened for the
    :data:`~cadrumo.core.external_constants.DEHU_RECHAZO_TACITO_DIAS_NATURALES` window is *rechazada*
    under Ley 39/2015 art. 43.2 — served, with every downstream plazo already
    running, even though the taxpayer never read it. That consequence attaches to
    the notification's delivery state, not to its
    :class:`~cadrumo.core.PostFilingEventKind`, so a plain ``notificacion`` whose
    concepto matches no sharper procedural pattern carries it just as a
    requerimiento does and cannot be reported through the kind-keyed
    :func:`overview_post_filing_event_notices` context map.

    The affected certificado ids ride on :attr:`Notice.context` beside the
    legal-catalogue entry that establishes the window, so a machine consumer keeps
    the structured list and an operator keeps the provenance. Empty when no
    notification has lapsed.
    """
    deemed_served = tuple(
        event for event in events if event.notificacion_estado_servicio is NotificacionEstadoServicio.RECHAZO_TACITO
    )
    if not deemed_served:
        return []
    certificado_ids = sorted({event.reference_id for event in deemed_served if event.reference_id})
    message = tr(
        "cli.overview.notificacion.rechazo_tacito_summary",
        default=(
            "%{count} AEAT notification(s) are legally served by rechazo tácito "
            "(Ley 39/2015 art. 43.2): %{certificados}. The plazos are already running."
        ),
        count=len(deemed_served),
        certificados=", ".join(certificado_ids),
    )
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=_DEEMED_SERVED_NOTICE_CODE,
            message=message,
            action=resolve_notice_action(action=ActionReference(action_id="operator.live.notifications.list")),
            context={
                "legal_ref": DEEMED_SERVED_LEGAL_REF,
                "certificado_ids": ",".join(certificado_ids),
                "count": str(len(deemed_served)),
            },
        ),
    ]


def _calendar_evidence_notice_with_action(notice: Notice) -> Notice:
    """Attach the concrete history-pull action at the CLI presentation boundary."""
    if notice.code != NO_AEAT_HISTORY_NOTICE_CODE:
        return notice
    return notice.model_copy(
        update={
            "action": resolve_notice_action(
                action=ActionReference(action_id="operator.live.filed.pull_all"),
            ),
        },
    )


def _calendar_entry_text_line(entry: OverviewCalendarEntry) -> str:
    return (
        f"{entry.modelo}\t{entry.period}\t{entry.user_state.value}"
        f"\topens={entry.opens_on.isoformat()}"
        f"\tcloses={entry.closes_on.isoformat()}"
        f"\tadjusted={entry.adjusted_closes_on.isoformat()}"
        f"\tshift={_calendar_shift_reason_text(entry.shift_reason)}"
        f"\tcenso_enrolment={entry.censo_enrolment_state.value}"
        f"\t{_calendar_filing_evidence_text_fields(entry.filing_evidence)}"
        f"\t{_calendar_entry_work_unit_text_fields(entry)}"
    )


def _calendar_suppressed_text_line(suppressed: SuppressedCalendarEntry) -> str:
    return (
        f"suppressed\t{suppressed.modelo}\t{suppressed.period}"
        f"\tverdict={suppressed.verdict.value}"
        f"\treason={suppressed.reason[:80]}"
    )


def _calendar_primary_lines_and_notices(cal: OverviewCalendar) -> tuple[list[str], list[Notice]]:
    lines = [_calendar_entry_text_line(entry) for entry in cal.entries]
    warning_notices = overview_calendar_warning_notices(cal.warnings)
    lines.extend(
        f"warning\t{warning.code}\t{warning_notice.message}"
        for warning, warning_notice in zip(cal.warnings, warning_notices, strict=True)
    )
    lines.extend(_calendar_event_text_line(event) for event in cal.events)
    if cal.completeness.computable_modelos:
        lines.append(
            f"computable\t{len(cal.completeness.computable_modelos)}"
            f"\tdefaulted\t{len(cal.completeness.defaulted_modelos)}",
        )
    lines.extend(_calendar_suppressed_text_line(suppressed) for suppressed in cal.suppressed_entries)
    return lines, list(warning_notices)


def _calendar_secondary_lines_and_notices(cal: OverviewCalendar) -> tuple[list[str], list[Notice]]:
    lines: list[str] = []
    notices: list[Notice] = []
    for notice in overview_coverage_notices(cal.coverage):
        lines.append(f"coverage_advised\t{len(cal.coverage.advised)}\t{notice.message}")
        notices.append(notice)
    for notice in overview_post_filing_event_notices(cal.events):
        lines.append(f"post_filing_pending\t{len(notice.context or {})}\t{notice.message}")
        notices.append(notice)
    for notice in overview_deemed_served_notification_notices(cal.events):
        context = notice.context or {}
        lines.append(f"notificacion_rechazo_tacito\t{context.get('count', '')}\t{notice.message}")
        notices.append(notice)
    return lines, notices


def _calendar_lines_and_notices(cal: OverviewCalendar) -> tuple[list[str], list[Notice]]:
    primary_lines, primary_notices = _calendar_primary_lines_and_notices(cal)
    secondary_lines, secondary_notices = _calendar_secondary_lines_and_notices(cal)
    return [*primary_lines, *secondary_lines], [*primary_notices, *secondary_notices]


def _profile_primary_lines_and_notices(
    cal: OverviewCalendar,
    *,
    label: str,
) -> tuple[list[str], list[Notice]]:
    lines = [_calendar_entry_text_line(entry) for entry in cal.entries]
    if not cal.taxpayer_model_declared:
        lines.append(
            f"warning\tINCOMPLETE_TAXPAYER_MODEL\t"
            f"{cal.incomplete_reason or tr('cli.overview.taxpayer_model_undeclared')}",
        )
    profile_warning_notices = overview_calendar_warning_notices(cal.warnings)
    lines.extend(
        f"warning\t{warning.code}\t{warning_notice.message}"
        for warning, warning_notice in zip(cal.warnings, profile_warning_notices, strict=True)
    )
    lines.extend(_calendar_event_text_line(event) for event in cal.events)
    lines.extend(_calendar_suppressed_text_line(suppressed) for suppressed in cal.suppressed_entries)
    notices = [
        notice.model_copy(update={"context": {**(notice.context or {}), "profile": label}})
        for notice in profile_warning_notices
    ]
    return lines, notices


def _profile_secondary_lines_and_notices(
    cal: OverviewCalendar,
    *,
    label: str,
) -> tuple[list[str], list[Notice]]:
    lines: list[str] = []
    notices: list[Notice] = []
    for notice in overview_coverage_notices(cal.coverage):
        tagged = notice.model_copy(update={"context": {**(notice.context or {}), "profile": label}})
        notices.append(tagged)
        lines.append(f"coverage_advised\t{label}\t{len(cal.coverage.advised)}\t{notice.message}")
    for notice in overview_post_filing_event_notices(cal.events):
        tagged = notice.model_copy(update={"context": {**(notice.context or {}), "profile": label}})
        notices.append(tagged)
        lines.append(f"post_filing_pending\t{label}\t{len(notice.context or {})}\t{notice.message}")
    for notice in overview_deemed_served_notification_notices(cal.events):
        context = notice.context or {}
        tagged = notice.model_copy(update={"context": {**context, "profile": label}})
        notices.append(tagged)
        lines.append(f"notificacion_rechazo_tacito\t{label}\t{context.get('count', '')}\t{notice.message}")
    return lines, notices


def _profile_calendar_lines_and_notices(
    cal: OverviewCalendar,
    *,
    label: str,
) -> tuple[list[str], list[Notice]]:
    primary_lines, primary_notices = _profile_primary_lines_and_notices(cal, label=label)
    secondary_lines, secondary_notices = _profile_secondary_lines_and_notices(cal, label=label)
    return [*primary_lines, *secondary_lines], [*primary_notices, *secondary_notices]


def overview_calendar_output(
    cal: OverviewCalendar,
    rng: OverviewCalendarRange,
    *,
    evidence_notices: Sequence[Notice],
) -> tuple[OverviewCalendarResult, list[str], list[Notice]]:
    """Project one active-profile calendar into payload, text lines, and notices."""
    entries = [
        OverviewCalendarEntryPayload.model_validate(
            {
                **entry.model_dump(mode="json"),
                "recovery": _recovery_payload(entry),
            },
        ).model_dump(mode="json")
        for entry in cal.entries
    ]
    events = [
        OverviewCalendarEventPayload.model_validate(event.model_dump(mode="json")).model_dump(mode="json")
        for event in cal.events
    ]
    typed_cal = OverviewCalendarResult.model_validate_json(
        json.dumps(
            {
                "range": cal.range.model_dump(mode="json"),
                "entries": entries,
                "events": events,
                "warnings": [
                    {
                        **warning.model_dump(mode="json"),
                        "fix_action": _resolved_action(warning.fix_action).model_dump(mode="json"),
                    }
                    for warning in cal.warnings
                ],
                "generated_at": cal.generated_at.isoformat(),
                "completeness": cal.completeness.model_dump(mode="json"),
                "taxpayer_model_declared": cal.taxpayer_model_declared,
                "incomplete_reason": cal.incomplete_reason,
                "suppressed_entries": [entry.model_dump(mode="json") for entry in cal.suppressed_entries],
                "coverage": cal.coverage.model_dump(mode="json"),
            },
        ),
    )
    lines: list[str] = [
        f"from\t{rng.from_date.isoformat()}",
        f"to\t{rng.to_date.isoformat()}",
        f"entries\t{len(cal.entries)}",
        f"events\t{len(cal.events)}",
    ]
    calendar_lines, calendar_notices = _calendar_lines_and_notices(cal)
    lines.extend(calendar_lines)
    for evidence_notice in evidence_notices:
        notice = _calendar_evidence_notice_with_action(evidence_notice)
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
    profile_lines, notices = _profile_calendar_lines_and_notices(cal, label=label)
    lines.extend(profile_lines)
    payload: dict[str, object] = {
        "profile_id": bucket_id,
        "label": label,
        "entry_count": len(cal.entries),
        "event_count": len(cal.events),
        "warning_count": len(cal.warnings),
        "suppressed_entry_count": len(cal.suppressed_entries),
    }
    next_due = _next_due_entry(cal)
    if next_due is not None:
        payload["next_due_modelo"] = next_due.modelo
        payload["next_due_period"] = str(next_due.period)
        payload["next_due_closes_on"] = next_due.adjusted_closes_on.isoformat()
    return payload, lines, notices


def _next_due_entry(cal: OverviewCalendar) -> OverviewCalendarEntry | None:
    """Return the earliest obligation closing at or after the window start.

    The window start is the query's own as-of anchor, so this is "next due" for
    the range the operator asked about rather than for the wall clock -- a
    historical window reports the first obligation inside it, not none.
    """
    upcoming = [entry for entry in cal.entries if entry.adjusted_closes_on >= cal.range.from_date]
    if not upcoming:
        return None
    return min(upcoming, key=lambda entry: entry.adjusted_closes_on)


def overview_agenda_output(agenda) -> tuple[OverviewAgendaResult, list[str], list[Notice]]:
    """Project an overview agenda into payload, text lines, and notices."""
    typed_agenda = strict_round_trip(OverviewAgendaResult, agenda)
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
    warning_notices = overview_calendar_warning_notices(agenda.warnings)
    for warning, warning_notice in zip(agenda.warnings, warning_notices, strict=True):
        lines.append(f"warning\t{warning.code}\t{warning_notice.message}")
    coverage_notices = overview_coverage_notices(agenda.coverage)
    for notice in coverage_notices:
        lines.append(f"coverage_advised\t{len(agenda.coverage.advised)}\t{notice.message}")
    return typed_agenda, lines, [*warning_notices, *coverage_notices]


def overview_backlog_output(
    backlog,
    *,
    work_units_notice: Notice | None,
) -> tuple[OverviewBacklogResult, list[str], list[Notice]]:
    """Project an overview backlog into payload, text lines, and notices."""
    typed_backlog = strict_round_trip(OverviewBacklogResult, backlog)
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
    warning_notices = overview_calendar_warning_notices(backlog.warnings)
    for warning, warning_notice in zip(backlog.warnings, warning_notices, strict=True):
        lines.append(f"warning\t{warning.code}\t{warning_notice.message}")
    coverage_notices = overview_coverage_notices(backlog.coverage)
    for notice in coverage_notices:
        lines.append(f"coverage_advised\t{len(backlog.coverage.advised)}\t{notice.message}")
    backlog_notices = [*warning_notices, *coverage_notices]
    if work_units_notice is not None:
        lines.append(f"work_units_degraded\t{work_units_notice.message}")
        backlog_notices.append(work_units_notice)
    return typed_backlog, lines, backlog_notices


def overview_explain_output(result) -> tuple[OverviewExplainResult, list[str]]:
    """Project an overview applicability explanation into payload and text lines."""
    typed_explain = strict_round_trip(OverviewExplainResult, result)
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
    resolved_by_step = {step.step_id: _resolved_action(step.next_action) for step in walkthrough.steps}
    typed_result = OverviewPrepareResult(
        modelo=walkthrough.modelo,
        filing_year=walkthrough.filing_year,
        period=walkthrough.period,
        steps=[
            OverviewPrepareStepPayload(
                step_id=step.step_id,
                state=step.state,
                summary=step.summary,
                next_action=resolved_by_step[step.step_id],
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
        resolved = resolved_by_step[step.step_id]
        # One notice per row that has somewhere to go, whatever its state: the
        # notice is what carries the executable line onto the text surface, so
        # emitting it selectively would show JSON an action text never sees.
        if resolved is None and step.state is _DataPrepStepState.DONE:
            continue
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code=f"overview.prepare.next_step.{step.step_id.value}",
                message=step.summary,
                action=resolved,
                context={"state": step.state.value},
            ),
        )
    return typed_result, lines, notices


def overview_pipeline_output(report, *, ledger) -> tuple[OverviewPipelineResult, list[str], list[Notice]]:
    """Project a pipeline-health report into payload, text lines, and notices."""
    resolved_by_modelo = {row.modelo: _resolved_action(row.next_action) for row in report.modelos}
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
                next_action=resolved_by_modelo[row.modelo],
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
        severity = NoticeSeverity.WARNING if row.state is ModeloReadinessState.BLOCKED else NoticeSeverity.INFO
        notices.append(
            Notice(
                severity=severity,
                code=f"overview.pipeline.modelo.{row.state.value}",
                message=row.summary,
                action=resolved_by_modelo[row.modelo],
                context={"modelo": row.modelo, "state": row.state.value},
            ),
        )
    lines.append("")
    lines.append(
        f"{tr('cli.overview.pipeline.labels.findings_section', default='Findings:')} "
        f"{report.total_blocking_findings} blocking, {report.total_warning_findings} warning",
    )
    return typed_result, lines, notices


def overview_status_output(report: OverviewStatusReport) -> tuple[list[str], list[Notice]]:
    """Project :class:`OverviewStatusReport` into text lines and notices.

    Both halves are built from one pass over
    :func:`~application.overview.build_overview_status_next_steps`: the text
    lines carry each row's localized explanation, the notices carry the same
    explanation plus the resolved action, and the shared envelope renders the
    executable text line from that same action.  There is no second decision
    procedure for either surface to drift from.

    Args:
        report: The assembled workspace status read model.

    Returns:
        The operator-facing text lines and the notices for the envelope.
    """
    next_step_notices = [_next_step_notice(step) for step in build_overview_status_next_steps(report)]
    lines: list[str] = [
        tr("cli.overview.status.title"),
        "",
        _profile_line(report),
        _transactions_line(report),
        _invoices_line(report),
        _drafts_line(report),
        _work_units_line(report),
        _storage_line(report),
        *_filing_obligation_lines(report),
        "",
        tr("cli.overview.status.next_heading"),
        *(f"  {notice.message}" for notice in next_step_notices),
    ]
    return lines, next_step_notices


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
                "in this local storage - your active modelo work is saved."
            ),
            count=report.work_units,
            discarded=report.discarded_work_units,
        )
    return tr(
        "cli.overview.status.work_units_present",
        default=("%{count} modelo work unit(s) are in progress in this local storage - your modelo work is saved."),
        count=report.work_units,
    )


def _profile_line(report: OverviewStatusReport) -> str:
    if report.active_profile_name is None:
        return tr("cli.overview.status.profile_missing")
    return tr("cli.overview.status.profile_active", profile=report.active_profile_name)


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


def _storage_line(report: OverviewStatusReport) -> str:
    """State the local-storage readability finding.

    The remedy is not stated here: unreadable rows raise a
    :attr:`~application.overview.OverviewStatusNextStepId.REPAIR_STORAGE`
    guidance row, which carries the diagnostics action through the same one
    projection every other row uses.
    """
    if report.unreadable_rows == 0:
        return tr("cli.overview.status.storage_ok")
    return tr("cli.overview.status.storage_warning", count=report.unreadable_rows)


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
    "DEEMED_SERVED_LEGAL_REF",
    "overview_agenda_output",
    "overview_backlog_output",
    "overview_calendar_output",
    "overview_calendar_profile_output",
    "overview_calendar_warning_notices",
    "overview_coverage_notices",
    "overview_deemed_served_notification_notices",
    "overview_explain_output",
    "overview_pipeline_output",
    "overview_post_filing_event_notices",
    "overview_prepare_output",
    "overview_status_output",
]
