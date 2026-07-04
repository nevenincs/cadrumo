"""CLI commands for the ``aeat app overview`` subcommand group.

Provides the ``status``, ``calendar``, ``agenda``, ``backlog``, ``explain``,
``prepare``, and ``pipeline`` verbs. All verbs are local-only: they never
contact AEAT and apply no mutations to stored state. Help strings are
localized via :func:`tr`; the docstrings here document internal logic and are
not surfaced as operator-facing CLI help.

This module is the transport adapter over the application overview builders:
:func:`build_overview_status_report`, :func:`build_overview_calendar`,
:func:`build_overview_calendar_events`,
:func:`calendar_events_from_modelo_records`,
:func:`calendar_filing_evidence_from_sources`,
:func:`~aeat.application.overview.build_data_prep_walkthrough`, and
:func:`~aeat.application.overview.build_pipeline_health_report`. Each command
emits a typed payload such as :class:`OverviewStatusResult`,
:class:`OverviewCalendarResult`, :class:`OverviewAgendaResult`,
:class:`OverviewBacklogResult`, :class:`OverviewExplainResult`,
:class:`OverviewPrepareResult`, or :class:`OverviewPipelineResult` through
:func:`_emit_envelope`. The ``pipeline`` verb resolves each period work
unit's current :class:`~aeat.domain.modelos.CalculationRevision` to derive its
readiness row.
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path

import typer

from ...application import overview as _overview_application
from ...application.overview import (
    DataPrepStepState as _DataPrepStepState,
)
from ...application.overview import (
    OverviewCalendar,
    OverviewCalendarEvent,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    build_overview_calendar,
    build_overview_calendar_events,
    calendar_events_from_modelo_records,
    calendar_filing_evidence_from_sources,
)
from ...core.external_constants import OutputLanguage
from ...core.hashing import sha256_hex
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.logging import get_logger
from ...domain.modelos import WorkUnit
from ._common import (
    _bad,
    _canonical_period,
    _emit_envelope,
    _load_drafts,
    _load_invoices,
    _no_active_profile_refusal,
    _parse_iso_date,
    _profile_to_taxpayer,
    _state,
    _tx_repo,
    activate_subcommand_output_language,
)
from ._overview_payloads import (
    OverviewAgendaResult,
    OverviewBacklogResult,
    OverviewCalendarResult,
    OverviewExplainResult,
    OverviewPipelineModeloPayload,
    OverviewPipelineResult,
    OverviewPrepareResult,
    OverviewPrepareStepPayload,
    OverviewStatusResult,
)
from ._overview_rendering import (
    overview_coverage_notices,
    overview_next_step_notices,
    overview_post_filing_event_notices,
    render_cli_overview_status_lines,
)

logger = get_logger(__name__)

app = typer.Typer(
    name="overview",
    help=tr("cli.overview.app_help"),
    no_args_is_help=True,
)


def _refuse_calendar_warnings(cal: OverviewCalendar) -> None:
    warning_summary = ", ".join(warning.code for warning in cal.warnings)
    raise _bad(
        tr(
            "cli.overview.calendar_refused_incomplete",
            keys=warning_summary,
        ),
    )


def _calendar_evidence_notice(code: str, message_key: str) -> Notice:
    """A WARNING notice for an optional calendar-evidence enrichment that failed to load.

    The persisted event / filing evidence rows only ANNOTATE the calendar's
    schedule-derived obligations (as observed AEAT events, or as filed). When a
    loader cannot read them the calendar must DEGRADE to a schedule-only view —
    over-reporting an obligation as still due, the safe direction — rather than
    refusing the whole calendar. Refusing left a never-filed taxpayer (who has no
    persisted evidence at all) unable to see the calendar of what they owe.
    """
    return Notice(severity=NoticeSeverity.WARNING, code=code, message=tr(message_key), context={})


def _local_live_calendar_events(
    bucket_id: str,
    rng: OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
) -> tuple[tuple[OverviewCalendarEvent, ...], Notice | None]:
    """Return ``(persisted-live event rows, degradation-notice-or-None)``.

    The CLI owns the bucket-scoped repository reads; the pure
    :func:`build_overview_calendar_events` builder performs the projection
    without contacting AEAT. A load failure degrades to no live-event rows plus a
    WARNING notice rather than refusing the whole calendar.
    """
    from ...adapters.persistence.profile.justificante import JustificanteRepository
    from ...application.live import ExpedientesService, JustificanteCaptureSnapshotService, NotificationsService

    try:
        expedientes = ExpedientesService().list_snapshots(bucket_id=bucket_id)
        notifications = NotificationsService().list_snapshots(bucket_id=bucket_id)
        justificante_captures = JustificanteCaptureSnapshotService(bucket_id=bucket_id).list_snapshots()
        justificantes = tuple(JustificanteRepository().iter_justificantes())
    except Exception:
        logger.warning(
            "overview calendar: live-event evidence unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        return (), _calendar_evidence_notice(
            "overview.calendar_live_events_degraded",
            message_key="cli.overview.calendar_local_live_events_unavailable",
        )
    events = build_overview_calendar_events(
        calendar_range=rng,
        expedientes_snapshots=tuple(expedientes),
        notification_snapshots=tuple(notifications),
        justificante_capture_snapshots=tuple(justificante_captures),
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )
    return events, None


def _local_modelo_record_calendar_events(
    bucket_id: str,
    rng: OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
) -> tuple[tuple[OverviewCalendarEvent, ...], Notice | None]:
    """Return ``(local-record event rows, degradation-notice-or-None)``.

    Delegates the DTO conversion to
    :func:`calendar_events_from_modelo_records` after loading bucket-local
    filing records and justificante metadata. A load failure degrades to no
    filing-event rows plus a WARNING notice rather than refusing the whole
    calendar.
    """
    try:
        from ...adapters.persistence.profile.justificante import JustificanteRepository
        from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository

        filing_records = tuple(ModeloRecordCatalogueRepository(bucket_id=bucket_id).load().values())
        justificantes = tuple(JustificanteRepository().iter_justificantes())
    except Exception:
        logger.warning(
            "overview calendar: modelo filing-event evidence unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        return (), _calendar_evidence_notice(
            "overview.calendar_modelo_events_degraded",
            message_key="cli.overview.calendar_local_modelo_events_unavailable",
        )
    events = calendar_events_from_modelo_records(
        filing_records,
        rng,
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )
    return events, None


def _local_modelo_work_units(bucket_id: str) -> tuple[tuple[WorkUnit, ...], Notice | None]:
    """Return ``(active work units, degradation notice-or-None)``.

    Work units are an OPTIONAL enrichment of the overview surfaces: they annotate
    schedule-derived entries as in-progress and widen the lookback window back to
    the oldest in-progress draft. The backlog and calendar themselves derive from
    the deadline schedule plus obligation applicability, so a work-unit load
    failure must DEGRADE the surface — proceed schedule-only — not refuse the
    whole answer.

    A fresh profile with no catalogue loads as empty (no failure). The failure
    path is a genuine work-unit-subsystem fault; degrading over-reports an
    in-progress draft as still-due (the safe direction — it surfaces more, never
    hides a due obligation) and only narrows the lookback to the default window.
    Refusing the entire overview because this optional enrichment failed left a
    behind-but-fresh taxpayer — the exact ``regularizar-atrasos`` persona — unable
    to answer "what have I missed"; the WARNING notice discloses the degradation
    instead.
    """
    try:
        from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
        from ...application.modelo import list_work_units

        repository = WorkUnitCatalogueRepository(bucket_id=bucket_id)
        return list_work_units(bucket_id=bucket_id, include_discarded=False, repository=repository), None
    except Exception:
        logger.warning(
            "overview: work-unit enrichment unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        notice = Notice(
            severity=NoticeSeverity.WARNING,
            code="overview.work_units_degraded",
            message=tr(
                "cli.overview.local_work_units_unavailable",
                default=(
                    "Local Modelo work-unit state could not be loaded; this overview is "
                    "derived from the deadline schedule and may over-report an in-progress "
                    "draft as still due or omit older in-progress drafts."
                ),
            ),
            context={},
        )
        return (), notice


def _live_censo_verified_profile_keys(record) -> tuple[str, ...]:
    """Return profile paths whose current value was stamped from live censo sync."""
    if record is None:
        return ()
    from ...application.user_profile import (
        CENSO_DERIVED_SOURCE_TAG,
        CENSO_SOURCE_TAG,
    )

    verified_sources = {CENSO_SOURCE_TAG, CENSO_DERIVED_SOURCE_TAG}
    return tuple(
        sorted(
            {fact.path for fact in record.facts if fact.path.strip() and fact.source in verified_sources},
        ),
    )


def _overview_status_period(period: str, *, year: int | None):
    """Resolve ``overview status --period`` through the registry-token union."""
    from ...core import (
        Period,
        PeriodError,
    )

    token = period.strip()
    if not token:
        raise _bad(tr("cli.common.errors.period_empty"))
    if year is None:
        raise _bad(tr("cli.common.errors.period_missing_year", token=token))
    try:
        return Period.from_year_and_code(year, token)
    except PeriodError as exc:
        raise _bad(tr("cli.common.errors.period_unrecognised", raw=period)) from exc


def _local_calendar_filing_evidence(
    bucket_id: str,
    events: tuple[OverviewCalendarEvent, ...],
    *,
    expected_tax_id: str | None = None,
) -> tuple[tuple[OverviewCalendarFilingEvidence, ...], Notice | None]:
    """Return ``(local/AEAT filing evidence rows, degradation-notice-or-None)``.

    The resulting :class:`OverviewCalendarFilingEvidence` rows feed
    :class:`OverviewCalendar` without treating a local filing record as proof of
    AEAT submission. A load failure degrades to no filing-evidence rows plus a
    WARNING notice rather than refusing the whole calendar.
    """
    try:
        from ...adapters.outbound.aeat.sede import FiledDeclaracionObservationStore
        from ...adapters.persistence.profile.justificante import JustificanteRepository
        from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
        from ...application.calculations import CalculationObservationRepository
        from ...application.live import JustificanteCaptureSnapshotService

        filing_records = tuple(ModeloRecordCatalogueRepository(bucket_id=bucket_id).load().values())
        justificantes = tuple(JustificanteRepository().iter_justificantes())
        justificante_captures = JustificanteCaptureSnapshotService(bucket_id=bucket_id).list_snapshots()
        filed_observation_store = FiledDeclaracionObservationStore(Path("var/aeat/filed-declarations"))
        filed_declaration_observations, verified_filed_artefact_csvs = (
            _calendar_verified_filed_declaration_observations(
                filed_observation_store,
                expected_tax_id=expected_tax_id,
            )
        )
        calculation_observations = tuple(CalculationObservationRepository().iter_records())
    except Exception:
        logger.warning(
            "overview calendar: filing evidence unavailable for bucket %s; deriving from schedule only",
            bucket_id,
            exc_info=True,
        )
        return (), _calendar_evidence_notice(
            "overview.calendar_filing_evidence_degraded",
            message_key="cli.overview.calendar_local_filing_evidence_unavailable",
        )
    evidence = calendar_filing_evidence_from_sources(
        filing_records=filing_records,
        observed_events=events,
        filed_declaration_observations=tuple(filed_declaration_observations),
        verified_filed_declaration_artefact_refs=tuple(verified_filed_artefact_csvs),
        verified_filed_declaration_artefact_csvs=verified_filed_artefact_csvs,
        calculation_observations=calculation_observations,
        justificante_capture_snapshots=tuple(justificante_captures),
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )
    return evidence, None


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


def _calendar_verified_filed_declaration_observations(
    store,
    *,
    expected_tax_id: str | None = None,
):
    """Return filed observations with justificante PDF refs proven parseable and matching."""
    verified_observations = []
    verified_artefact_csvs: dict[str, str] = {}
    for observation in store.list_observations():
        verified_artefacts = []
        for artefact in observation.artefacts:
            if artefact.kind != "justificante_pdf":
                verified_artefacts.append(artefact)
                continue
            csv = _stored_filed_artefact_matching_observation_csv(
                store,
                artefact,
                observation,
                expected_tax_id=expected_tax_id,
            )
            if csv is not None:
                if artefact.storage_ref is not None:
                    verified_artefact_csvs[artefact.storage_ref] = csv
                verified_artefacts.append(artefact)
                continue
            verified_artefacts.append(artefact.model_copy(update={"storage_ref": None}))
        verified_observations.append(observation.model_copy(update={"artefacts": tuple(verified_artefacts)}))
    return tuple(verified_observations), dict(sorted(verified_artefact_csvs.items()))


def _stored_filed_artefact_matching_observation_csv(
    store,
    artefact,
    observation,
    *,
    expected_tax_id: str | None,
) -> str | None:
    storage_ref = artefact.storage_ref
    if not storage_ref:
        return None
    try:
        body = store.load_artefact(storage_ref)
    except Exception:
        logger.warning(
            "overview calendar: ignored unreadable filed-declaration artefact %s",
            storage_ref,
            exc_info=True,
        )
        return None
    if len(body) != artefact.byte_count or sha256_hex(body) != artefact.sha256:
        return None
    return _stored_filed_justificante_matching_observation_csv(
        body,
        observation,
        storage_ref=storage_ref,
        expected_tax_id=expected_tax_id,
    )


def _stored_filed_justificante_matching_observation_csv(
    body: bytes,
    observation,
    *,
    storage_ref: str,
    expected_tax_id: str | None,
) -> str | None:
    from ...adapters.inbound.justificante import parse_justificante_bytes

    try:
        justificante = parse_justificante_bytes(body)
    except Exception:
        logger.warning(
            "overview calendar: ignored unparsable filed-declaration justificante artefact %s",
            storage_ref,
            exc_info=True,
        )
        return None

    expected = (expected_tax_id or observation.authenticated_identity or "").strip().upper()
    if not expected:
        return None
    if (
        justificante.modelo.strip() == observation.modelo
        and str(justificante.ejercicio or "").strip() == str(observation.ejercicio)
        and justificante.period == observation.period
        and justificante.tax_id.strip().upper() == expected
    ):
        return justificante.csv
    return None


@app.command("status", help=tr("cli.overview.status_help"))
def overview_status(
    ctx: typer.Context,
    period: str | None = typer.Option(None, "--period", help=tr("cli.overview.period_help")),
    year: int | None = typer.Option(
        None,
        "--year",
        help=tr("cli.overview.year_help", default="Filing year for --period (e.g. 2024)."),
    ),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.overview.verbose_help")),
) -> None:
    """Emit the overview status payload for readiness or per-period detail.

    The deadline-calendar surface that used to live behind `--calendar`
    is now the first-class `aeat app overview calendar` verb per the
    app-overview-shape ADR's Consequences section. No alternate flag path
    remains; callers must use the dedicated verb. The full-status branch projects
    :func:`build_overview_status_report`; the period branch emits only the
    matching draft rows.
    """
    from ...application.user_profile import record_to_values
    from ...core import resolve_active_bucket_id

    current = _state() if resolve_active_bucket_id() is not None else None
    if period is not None:
        if current is None:
            raise _no_active_profile_refusal()

        drafts = _load_drafts()
        canonical = _overview_status_period(period, year=year)
        wanted = (canonical.year, canonical.registry_token)

        def _draft_matches(draft_period: object) -> bool:
            # Drafts persist typed periods; compare their separate filing-year
            # and registry-token fields to the operator's ``--year``/``--period`` pair.
            return (
                getattr(draft_period, "year", None) == wanted[0]
                and getattr(draft_period, "registry_token", None) == wanted[1]
            )

        per_modelo_drafts = [d for d in drafts if _draft_matches(d.period)]
        from ._overview_payloads import OverviewDraftPayload

        period_display = f"{canonical.registry_token} {canonical.year}"
        typed_period = OverviewStatusResult(
            period=period_display,
            drafts=[
                OverviewDraftPayload(draft_id=d.draft_id, modelo=d.modelo, status=d.status.value)
                for d in per_modelo_drafts
            ],
            verbose=verbose,
        )
        period_lines: list[str] = [
            f"{tr('cli.overview.period')}\t{period_display}",
            f"{tr('cli.overview.drafts')}\t{len(per_modelo_drafts)}",
        ]
        for d in per_modelo_drafts:
            period_lines.append(f"{d.modelo}\t{d.draft_id}\t{d.status.value}")
        _emit_envelope(ctx, command="overview.status", result=typed_period, lines=period_lines)
        return
    profile_record = current.active_profile_record() if current is not None else None
    raw_values = record_to_values(profile_record) if profile_record is not None else None
    report = _overview_application.build_overview_status_report(state=current, raw_values=raw_values)
    typed_status = OverviewStatusResult.model_validate(report.model_dump(mode="json"))
    status_notices = list(overview_next_step_notices(report))
    coverage_lines: list[str] = []
    # ``status`` is a "what must I file" surface too: reconcile the active
    # profile's obligation coverage over the current year and surface the same
    # default advisory the calendar does, so status never reads as complete while
    # obligations go unscoped. The coverage report rides the Notice channel.
    if current is not None and current.active_profile_bucket_id() is not None:
        status_today = _date.today()
        status_cal = build_overview_calendar(
            _profile_to_taxpayer(current),
            OverviewCalendarRange(
                from_date=_date(status_today.year, 1, 1),
                to_date=_date(status_today.year, 12, 31),
            ),
            today=status_today,
            raw_values=raw_values,
        )
        for notice in overview_coverage_notices(status_cal.coverage):
            status_notices.append(notice)
            coverage_lines.append(f"coverage_advised\t{len(status_cal.coverage.advised)}\t{notice.message}")
    _emit_envelope(
        ctx,
        command="overview.status",
        result=typed_status,
        lines=[*render_cli_overview_status_lines(report), *coverage_lines],
        notices=status_notices,
    )


@app.command(
    "calendar",
    help=tr(
        "cli.overview.calendar.help",
        default=(
            "Render the deadline calendar for the active profile across the supplied "
            "date window. Applies festivos and business-day shifts. Local-only; never "
            "contacts AEAT."
        ),
    ),
)
def overview_calendar(
    ctx: typer.Context,
    from_date: str = typer.Option(
        ...,
        "--from",
        help=tr(
            "cli.overview.calendar.from_help",
            default="Inclusive start date for the calendar window (ISO YYYY-MM-DD).",
        ),
    ),
    to_date: str = typer.Option(
        ...,
        "--to",
        help=tr(
            "cli.overview.calendar.to_help",
            default="Inclusive end date for the calendar window (ISO YYYY-MM-DD).",
        ),
    ),
    allow_incomplete: bool = typer.Option(
        False,
        "--allow-incomplete",
        help=tr(
            "cli.overview.calendar.allow_incomplete_help",
            default="Render the calendar even when profile data is incomplete.",
        ),
    ),
    show_suppressed: bool = typer.Option(
        False,
        "--show-suppressed",
        help=tr(
            "cli.overview.calendar.show_suppressed_help",
            default=(
                "Include filtered (non-applicable) obligations in the output "
                "with their applicability verdict and reason."
            ),
        ),
    ),
    all_profiles: bool = typer.Option(
        False,
        "--all-profiles",
        help=tr(
            "cli.overview.calendar.all_profiles_help",
            default=(
                "Render the calendar for every registered active profile instead of "
                "the currently active one. Each profile's entries are emitted in a "
                "separate block with a leading profile header line."
            ),
        ),
    ),
    output_language: OutputLanguage | None = typer.Option(
        None,
        "--output-language",
        "--language",
        help=tr("cli.config.auth.output_language_help"),
    ),
) -> None:
    """Emit the overview calendar payload over the supplied date window.

    The command builds an :class:`OverviewCalendarRange`, enriches it with
    persisted :class:`OverviewCalendarEvent` and filing-evidence rows, and then
    delegates the legal calendar projection to :func:`build_overview_calendar`.
    """
    from ...application.user_profile import record_to_values

    activate_subcommand_output_language(ctx, output_language)

    rng = OverviewCalendarRange(
        from_date=_parse_iso_date(from_date, label="--from"),
        to_date=_parse_iso_date(to_date, label="--to"),
    )

    if all_profiles:
        _overview_calendar_all_profiles(
            ctx,
            rng=rng,
            allow_incomplete=allow_incomplete,
            show_suppressed=show_suppressed,
        )
        return

    current = _state()
    record = current.active_profile_record()
    raw_values = record_to_values(record) if record is not None else None
    bucket_id = current.active_profile_bucket_id()
    if bucket_id is None:
        raise _bad(tr("cli.config.errors.no_active_profile"))
    workflow_profile = _profile_to_taxpayer(current)
    evidence_notices: list[Notice] = []
    live_events, live_notice = _local_live_calendar_events(bucket_id, rng, expected_tax_id=workflow_profile.tax_id)
    modelo_record_events, modelo_events_notice = _local_modelo_record_calendar_events(
        bucket_id,
        rng,
        expected_tax_id=workflow_profile.tax_id,
    )
    events = (*live_events, *modelo_record_events)
    filing_evidence, filing_evidence_notice = _local_calendar_filing_evidence(
        bucket_id,
        events,
        expected_tax_id=workflow_profile.tax_id,
    )
    work_units, work_units_notice = _local_modelo_work_units(bucket_id)
    evidence_notices = [
        notice
        for notice in (live_notice, modelo_events_notice, filing_evidence_notice, work_units_notice)
        if notice is not None
    ]
    cal: OverviewCalendar = build_overview_calendar(
        workflow_profile,
        rng,
        today=_date.today(),
        raw_values=raw_values,
        show_suppressed=show_suppressed,
        events=events,
        filing_evidence=filing_evidence,
        work_units=work_units,
        live_censo_verified_profile_keys=_live_censo_verified_profile_keys(record),
    )
    if not cal.taxpayer_model_declared:
        # The taxpayer model is undeclared — the engine refuses
        # to guess. Surface the "declare your taxpayer type first"
        # guidance instead of an empty calendar with no explanation.
        raise _bad(cal.incomplete_reason or tr("cli.overview.taxpayer_model_undeclared"))
    if cal.warnings and not allow_incomplete:
        _refuse_calendar_warnings(cal)
    # ``coverage`` is surfaced through the typed ``Notice`` channel (the
    # canonical diagnostic surface), not as a bespoke payload field, so it is
    # excluded from the result dump the payload schema validates.
    cal_dump = cal.model_dump(mode="json", exclude={"coverage"})
    typed_cal = OverviewCalendarResult.model_validate(cal_dump)
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
    _emit_envelope(
        ctx,
        command="overview.calendar",
        result=typed_cal,
        lines=lines,
        notices=calendar_notices,
    )


def _overview_calendar_all_profiles(
    ctx: typer.Context,
    *,
    rng: OverviewCalendarRange,
    allow_incomplete: bool,
    show_suppressed: bool,
) -> None:
    """Emit the deadline calendar for every registered active profile.

    Iterates :func:`list_profile_buckets`, loads each active bucket's profile
    record inside its own :func:`profile_storage_session`, and calls
    :func:`build_overview_calendar` once per profile. Unreadable buckets are
    skipped with a warning line; they do not abort the scan. The combined JSON
    payload still uses the single :class:`OverviewCalendarResult` schema
    registered for ``overview.calendar``.
    """
    from ...adapters.persistence.storage.bucket import BucketLifecycleStatus
    from ...application.user_profile import (
        ProfileRepository,
        profile_storage_session,
        projection_for_taxpayer,
        record_to_values,
    )
    from ...application.workflow import list_profile_buckets

    today = _date.today()
    buckets = list_profile_buckets()
    active_buckets = {bid: ptr for bid, ptr in buckets.items() if ptr.status is BucketLifecycleStatus.ACTIVE}

    all_lines: list[str] = [
        f"from\t{rng.from_date.isoformat()}",
        f"to\t{rng.to_date.isoformat()}",
        f"profiles\t{len(active_buckets)}",
    ]
    all_calendars: list[dict[str, object]] = []
    all_coverage_notices: list[Notice] = []

    repository = ProfileRepository()
    for bucket_id, pointer in sorted(active_buckets.items(), key=lambda kv: kv[1].label):
        try:
            with profile_storage_session(bucket_id):
                record = repository.load(bucket_id)
                raw_values = record_to_values(record.record)
                taxpayer = projection_for_taxpayer(record.record, tax_id_default="00000000T")
                live_censo_verified_profile_keys = _live_censo_verified_profile_keys(record.record)
                # The multi-profile view already degrades per profile (it skips an
                # unreadable one below) and renders many calendars in one payload,
                # so the per-loader degradation notices are dropped here; each
                # loader still returns schedule-only evidence rather than raising.
                live_events, _ = _local_live_calendar_events(bucket_id, rng, expected_tax_id=taxpayer.tax_id)
                modelo_record_events, _ = _local_modelo_record_calendar_events(
                    bucket_id,
                    rng,
                    expected_tax_id=taxpayer.tax_id,
                )
                events = (*live_events, *modelo_record_events)
                filing_evidence, _ = _local_calendar_filing_evidence(
                    bucket_id,
                    events,
                    expected_tax_id=taxpayer.tax_id,
                )
                work_units, _ = _local_modelo_work_units(bucket_id)
        except typer.BadParameter:
            raise
        except Exception:
            logger.warning(
                "overview calendar: skipping unreadable profile %s (%s)",
                bucket_id,
                pointer.label,
                exc_info=True,
            )
            all_lines.append(f"profile_skipped\t{bucket_id}\t{pointer.label}")
            continue

        cal = build_overview_calendar(
            taxpayer,
            rng,
            today=today,
            raw_values=raw_values,
            show_suppressed=show_suppressed,
            events=events,
            filing_evidence=filing_evidence,
            work_units=work_units,
            live_censo_verified_profile_keys=live_censo_verified_profile_keys,
        )

        all_lines.append(f"profile\t{bucket_id}\t{pointer.label}")
        all_lines.append(f"entries\t{len(cal.entries)}")
        all_lines.append(f"events\t{len(cal.events)}")
        for entry in cal.entries:
            all_lines.append(
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
            all_lines.append(
                f"warning\tINCOMPLETE_TAXPAYER_MODEL\t"
                f"{cal.incomplete_reason or tr('cli.overview.taxpayer_model_undeclared')}",
            )
        if cal.warnings and not allow_incomplete:
            _refuse_calendar_warnings(cal)
        for warning in cal.warnings:
            all_lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
        for event in cal.events:
            all_lines.append(_calendar_event_text_line(event))
        for suppressed in cal.suppressed_entries:
            all_lines.append(
                f"suppressed\t{suppressed.modelo}\t{suppressed.period}"
                f"\tverdict={suppressed.verdict.value}"
                f"\treason={suppressed.reason[:80]}",
            )
        for notice in overview_coverage_notices(cal.coverage):
            # Attribute the advisory to its profile so the multi-profile
            # envelope keeps each profile's coverage gap distinguishable.
            tagged = notice.model_copy(update={"context": {**(notice.context or {}), "profile": pointer.label}})
            all_coverage_notices.append(tagged)
            all_lines.append(f"coverage_advised\t{pointer.label}\t{len(cal.coverage.advised)}\t{notice.message}")
        for notice in overview_post_filing_event_notices(cal.events):
            tagged = notice.model_copy(update={"context": {**(notice.context or {}), "profile": pointer.label}})
            all_coverage_notices.append(tagged)
            all_lines.append(f"post_filing_pending\t{pointer.label}\t{len(notice.context or {})}\t{notice.message}")

        all_calendars.append(
            {
                "profile_id": bucket_id,
                "label": pointer.label,
                "calendar": cal.model_dump(mode="json", exclude={"coverage"}),
            },
        )

    typed_all = OverviewCalendarResult.model_validate({"profiles": all_calendars})
    _emit_envelope(ctx, command="overview.calendar", result=typed_all, lines=all_lines, notices=all_coverage_notices)


@app.command(
    "agenda",
    help=tr(
        "cli.overview.agenda.help",
        default=(
            "Rank upcoming and past-due obligations around an as-of date. "
            "Surfaces a single `next_due` plus due-today / due-soon / overdue cohorts. "
            "Local-only; never contacts AEAT."
        ),
    ),
)
def overview_agenda(
    ctx: typer.Context,
    as_of: str | None = typer.Option(
        None,
        "--date",
        help=tr(
            "cli.overview.agenda.date_help",
            default="As-of date for the agenda (ISO YYYY-MM-DD); defaults to today.",
        ),
    ),
    horizon_days: int = typer.Option(
        14,
        "--horizon",
        help=tr(
            "cli.overview.agenda.horizon_help",
            default="Forward window (days) the `due_soon` cohort honours.",
        ),
    ),
    allow_incomplete: bool = typer.Option(
        False,
        "--allow-incomplete",
        help=tr(
            "cli.overview.agenda.allow_incomplete_help",
            default="Render the agenda even when profile data is incomplete.",
        ),
    ),
) -> None:
    """Emit the overview agenda payload with next-due cohort breakdowns.

    The command delegates obligation ranking to :func:`build_overview_agenda`
    and only adapts the application DTO to the CLI envelope and tabular text
    lines.
    """
    from ...application.overview import build_overview_agenda
    from ...application.user_profile import record_to_values

    current = _state()
    as_of_date = _parse_iso_date(as_of, label="--date") if as_of else _date.today()
    if horizon_days <= 0:
        raise _bad(
            tr(
                "cli.overview.agenda.errors.invalid_horizon",
                default="--horizon must be a positive integer (days).",
            ),
        )
    record = current.active_profile_record()
    raw_values = record_to_values(record) if record is not None else None
    agenda = build_overview_agenda(
        _profile_to_taxpayer(current),
        as_of=as_of_date,
        horizon_days=horizon_days,
        raw_values=raw_values,
    )
    if not agenda.taxpayer_model_declared and not allow_incomplete:
        raise _bad(agenda.incomplete_reason or tr("cli.overview.taxpayer_model_undeclared"))
    if agenda.warnings and not allow_incomplete:
        warning_summary = ", ".join(warning.code for warning in agenda.warnings)
        raise _bad(
            tr(
                "cli.overview.calendar_refused_incomplete",
                keys=warning_summary,
            ),
        )

    typed_agenda = OverviewAgendaResult.model_validate(agenda.model_dump(mode="json", exclude={"coverage"}))
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
    _emit_envelope(ctx, command="overview.agenda", result=typed_agenda, lines=lines, notices=coverage_notices)


@app.command(
    "backlog",
    help=tr(
        "cli.overview.backlog.help",
        default=(
            "List past-due obligations the operator has not yet filed. Sorted oldest "
            "first so the most-overdue items triage first. Local-only; never contacts AEAT."
        ),
    ),
)
def overview_backlog(
    ctx: typer.Context,
    from_date: str | None = typer.Option(
        None,
        "--from",
        help=tr(
            "cli.overview.backlog.from_help",
            default="Inclusive start date (ISO YYYY-MM-DD); defaults to 365 days before today.",
        ),
    ),
    to_date: str | None = typer.Option(
        None,
        "--to",
        help=tr(
            "cli.overview.backlog.to_help",
            default="Inclusive end date (ISO YYYY-MM-DD); defaults to today.",
        ),
    ),
    allow_incomplete: bool = typer.Option(
        False,
        "--allow-incomplete",
        help=tr(
            "cli.overview.backlog.allow_incomplete_help",
            default="Render the backlog even when profile data is incomplete.",
        ),
    ),
) -> None:
    """Emit the overview backlog payload for past-due obligations.

    The command delegates read-model assembly to
    :func:`build_overview_backlog`; it does not resume or mutate modelo
    workflows.
    """
    from ...application.overview import build_overview_backlog
    from ...application.user_profile import record_to_values

    current = _state()
    parsed_from = _parse_iso_date(from_date, label="--from") if from_date else None
    parsed_to = _parse_iso_date(to_date, label="--to") if to_date else None
    record = current.active_profile_record()
    raw_values = record_to_values(record) if record is not None else None
    bucket_id = current.active_profile_bucket_id()
    if bucket_id is None:
        raise _bad(tr("cli.config.errors.no_active_profile"))
    work_units, work_units_notice = _local_modelo_work_units(bucket_id)
    backlog = build_overview_backlog(
        _profile_to_taxpayer(current),
        from_date=parsed_from,
        to_date=parsed_to,
        raw_values=raw_values,
        work_units=work_units,
    )
    if not backlog.taxpayer_model_declared:
        raise _bad(backlog.incomplete_reason or tr("cli.overview.taxpayer_model_undeclared"))
    if backlog.warnings and not allow_incomplete:
        warning_summary = ", ".join(warning.code for warning in backlog.warnings)
        raise _bad(
            tr(
                "cli.overview.calendar_refused_incomplete",
                keys=warning_summary,
            ),
        )

    typed_backlog = OverviewBacklogResult.model_validate(backlog.model_dump(mode="json", exclude={"coverage"}))
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
    _emit_envelope(ctx, command="overview.backlog", result=typed_backlog, lines=lines, notices=backlog_notices)


@app.command(
    "explain",
    help=tr(
        "cli.overview.explain.help",
        default=(
            "Decompose a modelo's applicability against the active profile. Surfaces "
            "the binary applicable flag, the registry-backed rationale text, and the "
            "profile facts the decision depends on. Local-only; never contacts AEAT."
        ),
    ),
)
def overview_explain(
    ctx: typer.Context,
    modelo: str = typer.Argument(
        ...,
        help=tr(
            "cli.overview.explain.modelo_help",
            default="AEAT modelo identifier (e.g. 303, 130, 100).",
        ),
    ),
    year: int | None = typer.Option(
        None,
        "--year",
        help=tr(
            "cli.overview.explain.year_help",
            default="Fiscal year for the applicability evaluation; defaults to the current year.",
        ),
    ),
) -> None:
    """Emit the overview explain payload for one modelo applicability verdict.

    The explanation comes from :func:`build_overview_explain`; this adapter only
    maps application errors to CLI validation and renders the typed envelope.
    """
    from ...application.overview import OverviewExplainError, build_overview_explain

    current = _state()
    try:
        result = build_overview_explain(
            _profile_to_taxpayer(current),
            modelo=modelo,
            year=year,
        )
    except OverviewExplainError as exc:
        raise _bad(str(exc)) from exc
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
    for fact_name, fact_value in sorted(result.profile_facts.items()):
        lines.append(f"profile_fact\t{fact_name}\t{fact_value}")
    _emit_envelope(ctx, command="overview.explain", result=typed_explain, lines=lines)


@app.command(
    "prepare",
    help=tr(
        "cli.overview.prepare.help",
        default=(
            "Walk through the data-preparation steps for one modelo/period in order: "
            "import transactions, classify them, attach purchase-invoice evidence, "
            "register business invoices, resolve ledger readiness gaps, then start or "
            "resume the modelo work unit. Shows each step's current progress and the "
            "exact next command to run. Read-only; safe to run repeatedly; never "
            "contacts AEAT."
        ),
    ),
)
def overview_prepare(
    ctx: typer.Context,
    modelo: str = typer.Option(
        ...,
        "--modelo",
        help=tr(
            "cli.overview.prepare.modelo_help",
            default="AEAT modelo identifier to prepare data for (e.g. 130, 303, 100).",
        ),
    ),
    year: int = typer.Option(
        ...,
        "--year",
        help=tr("cli.overview.prepare.year_help", default="Filing year (e.g. 2026)."),
    ),
    period: str = typer.Option(
        ...,
        "--period",
        help=tr(
            "cli.overview.prepare.period_help",
            default=(
                "Filing period as an AEAT token: 1T-4T (quarters), 0A (annual), "
                "01-12 (months). Combine with --year to choose the year."
            ),
        ),
    ),
) -> None:
    """Emit the ordered data-prep walkthrough for one (modelo, period) scope.

    Delegates the readiness composition to
    :func:`~aeat.application.overview.build_data_prep_walkthrough`; this
    adapter resolves the active bucket, validates the modelo/period against
    the registry, loads the ledger/invoice/evidence/work-unit state, and
    renders the typed envelope plus per-step next-command notices.
    """
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.ledger import PurchaseInvoiceEvidenceService, preflight_ledger_tax_readiness
    from ...application.modelo import list_work_units, registry_describe_modelo_for_scope
    from ...application.overview import build_data_prep_walkthrough
    from ...domain.calculations.registry import RegistrySnapshotError

    current = _state()
    bucket_id = current.active_profile_bucket_id()
    if bucket_id is None:
        raise _no_active_profile_refusal()

    canonical_period = _canonical_period(period, year=year)
    try:
        registry_describe_modelo_for_scope(modelo, period=canonical_period)
    except (ValueError, RegistrySnapshotError) as exc:
        raise _bad(
            tr(
                "cli.overview.prepare.modelo_period_error",
                message=str(exc),
                default="{message}",
            ),
        ) from exc

    transaction_repository = _tx_repo(current)
    invoice_catalogue = _load_invoices()
    evidence_records = PurchaseInvoiceEvidenceService().list_all(bucket_id=bucket_id)
    preflight_report = preflight_ledger_tax_readiness(
        bucket_id=bucket_id,
        period=canonical_period,
        transaction_repository=transaction_repository,
    )
    work_units = list_work_units(
        bucket_id=bucket_id,
        include_discarded=False,
        repository=WorkUnitCatalogueRepository(bucket_id=bucket_id),
    )

    walkthrough = build_data_prep_walkthrough(
        bucket_id=bucket_id,
        modelo=modelo,
        period=canonical_period,
        transaction_repository=transaction_repository,
        invoice_catalogue=invoice_catalogue,
        evidence_records=evidence_records,
        preflight_report=preflight_report,
        work_units=work_units,
    )

    typed_result = OverviewPrepareResult(
        modelo=walkthrough.modelo,
        filing_year=walkthrough.filing_year,
        period=walkthrough.period,
        steps=[
            OverviewPrepareStepPayload(
                step_id=step.step_id.value,
                state=step.state.value,
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
    _emit_envelope(ctx, command="overview.prepare", result=typed_result, lines=lines, notices=notices)


@app.command(
    "pipeline",
    help=tr(
        "cli.overview.pipeline.help",
        default=(
            "Show cross-domain pipeline health for one filing period in one table: "
            "ledger classification/review state, modelo readiness (calculated / "
            "verified / filed / blocked) for every work unit in the period, and "
            "outstanding verification findings. Read-only; safe to run repeatedly; "
            "never contacts AEAT."
        ),
    ),
)
def overview_pipeline(
    ctx: typer.Context,
    year: int = typer.Option(
        ...,
        "--year",
        help=tr("cli.overview.pipeline.year_help", default="Filing year (e.g. 2026)."),
    ),
    period: str = typer.Option(
        ...,
        "--period",
        help=tr(
            "cli.overview.pipeline.period_help",
            default=(
                "Filing period as an AEAT token: 1T-4T (quarters), 0A (annual), "
                "01-12 (months). Combine with --year to choose the year."
            ),
        ),
    ),
) -> None:
    """Emit the cross-domain pipeline health report for one (filing_year, period) scope.

    Delegates the readiness composition to
    :func:`~aeat.application.overview.build_pipeline_health_report`; this
    adapter resolves the active bucket, loads the period-scoped ledger status
    report, the period's modelo work units, their current calculation
    revisions, and the latest verification report per revision, then renders
    the typed envelope plus outstanding-finding notices.
    """
    from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
    from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
    from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
    from ...application.ledger import summarize_manual_transactions
    from ...application.modelo import get_calculation_revision, list_verification_reports, list_work_units
    from ...application.overview import ModeloReadinessState, build_pipeline_health_report
    from ...domain.modelos import CalculationRevision, VerificationReport
    from ._ledger_payloads import LedgerStatusResult

    current = _state()
    bucket_id = current.active_profile_bucket_id()
    if bucket_id is None:
        raise _no_active_profile_refusal()

    canonical_period = _canonical_period(period, year=year)
    transaction_repository = _tx_repo(current)
    ledger_report = summarize_manual_transactions(
        bucket_id=bucket_id,
        period=canonical_period,
        transaction_repository=transaction_repository,
    )

    all_work_units = list_work_units(
        bucket_id=bucket_id,
        include_discarded=False,
        repository=WorkUnitCatalogueRepository(bucket_id=bucket_id),
    )
    work_units = tuple(
        unit
        for unit in all_work_units
        if unit.filing_year == canonical_period.filing_year
        and unit.period.registry_token == canonical_period.registry_token
    )

    calculation_repository = CalculationRevisionCatalogueRepository(bucket_id=bucket_id)
    verification_repository = VerificationReportCatalogueRepository(bucket_id=bucket_id)
    revisions_by_id: dict[str, CalculationRevision] = {}
    reports_by_revision_id: dict[str, tuple[VerificationReport, ...]] = {}
    for unit in work_units:
        if unit.current_calculation_revision_id is None:
            continue
        revision = get_calculation_revision(
            unit.current_calculation_revision_id,
            calculation_repository=calculation_repository,
        )
        revisions_by_id[revision.calculation_revision_id] = revision
        reports_by_revision_id[revision.calculation_revision_id] = list_verification_reports(
            calculation_revision_id=revision.calculation_revision_id,
            verification_repository=verification_repository,
        )

    report = build_pipeline_health_report(
        bucket_id=bucket_id,
        filing_year=canonical_period.filing_year,
        period=canonical_period,
        ledger_report=ledger_report,
        work_units=work_units,
        revisions_by_id=revisions_by_id,
        reports_by_revision_id=reports_by_revision_id,
    )

    typed_result = OverviewPipelineResult(
        filing_year=report.filing_year,
        period=report.period,
        ledger=LedgerStatusResult.model_validate(report.ledger.model_dump(mode="json")),
        modelos=[
            OverviewPipelineModeloPayload(
                modelo=row.modelo,
                work_unit_id=row.work_unit_id,
                state=row.state.value,
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

    _emit_envelope(ctx, command="overview.pipeline", result=typed_result, lines=lines, notices=notices)
