"""CLI commands for the ``aeat app overview`` subcommand group.

Provides the ``status``, ``calendar``, ``agenda``, ``backlog``, and
``explain`` verbs. All verbs are local-only: they never contact AEAT
and apply no mutations to stored state. Help strings are localized via
:func:`~aeat.core.i18n.tr`; the docstrings here document internal
logic and are not surfaced as operator-facing CLI help.
"""

from __future__ import annotations

from datetime import date as _date
from pathlib import Path

import typer

from ...application.overview import (
    OverviewCalendar,
    OverviewCalendarEvent,
    OverviewCalendarRange,
    build_overview_calendar,
    build_overview_calendar_events,
    build_overview_status_report,
    calendar_events_from_modelo_records,
    calendar_filing_evidence_from_sources,
)
from ...core.hashing import sha256_hex
from ...core.i18n import tr
from ...core.logging import get_logger
from ._common import (
    _bad,
    _emit_envelope,
    _load_drafts,
    _no_active_profile_refusal,
    _parse_iso_date,
    _profile_to_taxpayer,
    _state,
)
from ._overview_payloads import (
    OverviewAgendaResult,
    OverviewBacklogResult,
    OverviewCalendarResult,
    OverviewExplainResult,
    OverviewStatusResult,
)
from ._overview_rendering import overview_next_step_notices, render_cli_overview_status_lines

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


def _local_live_calendar_events(
    bucket_id: str,
    rng: OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
):
    """Return observed calendar events from local persisted live-read snapshots."""
    from ...application.live import ExpedientesService, JustificanteCaptureSnapshotService, NotificationsService
    from ...domain.justificante import JustificanteRepository

    try:
        expedientes = ExpedientesService().list_snapshots(bucket_id=bucket_id)
        notifications = NotificationsService().list_snapshots(bucket_id=bucket_id)
        justificante_captures = JustificanteCaptureSnapshotService(bucket_id=bucket_id).list_snapshots()
        justificantes = tuple(JustificanteRepository().iter_justificantes())
    except Exception as exc:
        logger.warning(
            "overview calendar: failed to load local live snapshots for bucket %s",
            bucket_id,
            exc_info=True,
        )
        raise _bad(
            tr(
                "cli.overview.calendar_local_live_events_unavailable",
                default=(
                    "Overview calendar local live-event evidence is unavailable; "
                    "refusing to render without persisted AEAT event state."
                ),
            ),
        ) from exc
    return build_overview_calendar_events(
        calendar_range=rng,
        expedientes_snapshots=tuple(expedientes),
        notification_snapshots=tuple(notifications),
        justificante_capture_snapshots=tuple(justificante_captures),
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )


def _local_modelo_record_calendar_events(
    bucket_id: str,
    rng: OverviewCalendarRange,
    *,
    expected_tax_id: str | None = None,
):
    """Return observed calendar events from persisted local Modelo filing records."""
    try:
        from ...domain.justificante import JustificanteRepository
        from ...domain.modelos import ModeloRecordCatalogueRepository

        filing_records = tuple(ModeloRecordCatalogueRepository(bucket_id=bucket_id).load().values())
        justificantes = tuple(JustificanteRepository().iter_justificantes())
    except Exception as exc:
        logger.warning(
            "overview calendar: failed to load local modelo filing events for bucket %s",
            bucket_id,
            exc_info=True,
        )
        raise _bad(
            tr(
                "cli.overview.calendar_local_modelo_events_unavailable",
                default=(
                    "Overview calendar local Modelo filing events are unavailable; "
                    "refusing to render without persisted filing state."
                ),
            ),
        ) from exc
    return calendar_events_from_modelo_records(
        filing_records,
        rng,
        justificantes=justificantes,
        expected_tax_id=expected_tax_id,
    )


def _live_censo_verified_profile_keys(record) -> tuple[str, ...]:
    """Return profile paths whose current value was stamped from live censo sync."""
    if record is None:
        return ()
    from ...application.user_profile import CENSO_DERIVED_SOURCE_TAG, CENSO_SOURCE_TAG

    verified_sources = {CENSO_SOURCE_TAG, CENSO_DERIVED_SOURCE_TAG}
    return tuple(
        sorted(
            {fact.path for fact in record.facts if fact.path.strip() and fact.source in verified_sources},
        ),
    )


def _overview_status_period(period: str, *, year: int | None):
    """Resolve ``overview status --period`` through the registry-token union."""
    from ...core import Period, PeriodError

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
):
    """Return local/AEAT filing evidence rows from persisted local stores."""
    try:
        from ...adapters.outbound.aeat.sede._observation_store import FiledDeclaracionObservationStore
        from ...application.calculations import CalculationObservationRepository
        from ...application.live import JustificanteCaptureSnapshotService
        from ...domain.justificante import JustificanteRepository
        from ...domain.modelos import ModeloRecordCatalogueRepository

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
    except Exception as exc:
        logger.warning(
            "overview calendar: failed to load local filing evidence for bucket %s",
            bucket_id,
            exc_info=True,
        )
        raise _bad(
            tr(
                "cli.overview.calendar_local_filing_evidence_unavailable",
                default=(
                    "Overview calendar local filing evidence is unavailable; "
                    "refusing to render without persisted AEAT filing state."
                ),
            ),
        ) from exc
    return calendar_filing_evidence_from_sources(
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
    """Render workspace readiness or per-period detail.

    The deadline-calendar surface that used to live behind `--calendar`
    is now the first-class `aeat app overview calendar` verb per the
    app-overview-shape ADR's Consequences section. No compatibility
    shim is preserved; callers must use the dedicated verb.
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
    report = build_overview_status_report(state=current, raw_values=raw_values)
    typed_status = OverviewStatusResult.model_validate(report.model_dump(mode="json"))
    _emit_envelope(
        ctx,
        command="overview.status",
        result=typed_status,
        lines=render_cli_overview_status_lines(report),
        notices=overview_next_step_notices(report),
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
) -> None:
    """Render the deadline calendar over the supplied window."""
    from ...application.user_profile import record_to_values

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
    live_events = _local_live_calendar_events(bucket_id, rng, expected_tax_id=workflow_profile.tax_id)
    modelo_record_events = _local_modelo_record_calendar_events(
        bucket_id,
        rng,
        expected_tax_id=workflow_profile.tax_id,
    )
    events = (*live_events, *modelo_record_events)
    filing_evidence = _local_calendar_filing_evidence(
        bucket_id,
        events,
        expected_tax_id=workflow_profile.tax_id,
    )
    cal: OverviewCalendar = build_overview_calendar(
        workflow_profile,
        rng,
        today=_date.today(),
        raw_values=raw_values,
        show_suppressed=show_suppressed,
        events=events,
        filing_evidence=filing_evidence,
        live_censo_verified_profile_keys=_live_censo_verified_profile_keys(record),
    )
    if not cal.taxpayer_model_declared:
        # The taxpayer model is undeclared — the engine refuses
        # to guess. Surface the "declare your taxpayer type first"
        # guidance instead of an empty calendar with no explanation.
        raise _bad(cal.incomplete_reason or tr("cli.overview.taxpayer_model_undeclared"))
    if cal.warnings and not allow_incomplete:
        _refuse_calendar_warnings(cal)
    cal_dump = cal.model_dump(mode="json")
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
            f"\tshift={entry.shift_reason}"
            f"\tcenso_enrolment={entry.censo_enrolment_state.value}"
            f"\t{_calendar_filing_evidence_text_fields(entry.filing_evidence)}",
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
    _emit_envelope(ctx, command="overview.calendar", result=typed_cal, lines=lines)


def _overview_calendar_all_profiles(
    ctx: typer.Context,
    *,
    rng: OverviewCalendarRange,
    allow_incomplete: bool,
    show_suppressed: bool,
) -> None:
    """Emit the deadline calendar for every registered active profile.

    Iterates :func:`list_profile_buckets`, loads each active bucket's
    profile record inside its own :func:`profile_storage_session`, and
    calls :func:`build_overview_calendar` once per profile. Unreadable
    buckets are skipped with a warning line; they do not abort the scan.
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

    repository = ProfileRepository()
    for bucket_id, pointer in sorted(active_buckets.items(), key=lambda kv: kv[1].label):
        try:
            with profile_storage_session(bucket_id):
                record = repository.load(bucket_id)
                raw_values = record_to_values(record.record)
                taxpayer = projection_for_taxpayer(record.record, tax_id_default="00000000T")
                live_censo_verified_profile_keys = _live_censo_verified_profile_keys(record.record)
                live_events = _local_live_calendar_events(bucket_id, rng, expected_tax_id=taxpayer.tax_id)
                modelo_record_events = _local_modelo_record_calendar_events(
                    bucket_id,
                    rng,
                    expected_tax_id=taxpayer.tax_id,
                )
                events = (*live_events, *modelo_record_events)
                filing_evidence = _local_calendar_filing_evidence(
                    bucket_id,
                    events,
                    expected_tax_id=taxpayer.tax_id,
                )
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
                f"\tshift={entry.shift_reason}"
                f"\tcenso_enrolment={entry.censo_enrolment_state.value}"
                f"\t{_calendar_filing_evidence_text_fields(entry.filing_evidence)}",
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

        all_calendars.append(
            {
                "profile_id": bucket_id,
                "label": pointer.label,
                "calendar": cal.model_dump(mode="json"),
            },
        )

    typed_all = OverviewCalendarResult.model_validate({"profiles": all_calendars})
    _emit_envelope(ctx, command="overview.calendar", result=typed_all, lines=all_lines)


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
    """Surface the operator's next-due obligation with cohort breakdowns."""
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
    _emit_envelope(ctx, command="overview.agenda", result=typed_agenda, lines=lines)


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
    """Surface the operator's past-due backlog without mutating state."""
    from ...application.overview import build_overview_backlog
    from ...application.user_profile import record_to_values

    current = _state()
    parsed_from = _parse_iso_date(from_date, label="--from") if from_date else None
    parsed_to = _parse_iso_date(to_date, label="--to") if to_date else None
    record = current.active_profile_record()
    raw_values = record_to_values(record) if record is not None else None
    backlog = build_overview_backlog(
        _profile_to_taxpayer(current),
        from_date=parsed_from,
        to_date=parsed_to,
        raw_values=raw_values,
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

    typed_backlog = OverviewBacklogResult.model_validate(backlog.model_dump(mode="json"))
    lines: list[str] = [
        f"from\t{backlog.range.from_date.isoformat()}",
        f"to\t{backlog.range.to_date.isoformat()}",
        f"as_of\t{backlog.as_of.isoformat()}",
        f"late_count\t{backlog.late_count}",
    ]
    for entry in backlog.items:
        lines.append(f"{entry.modelo}\t{entry.period}\tcloses={entry.adjusted_closes_on.isoformat()}")
    for warning in backlog.warnings:
        lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
    _emit_envelope(ctx, command="overview.backlog", result=typed_backlog, lines=lines)


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
    """Explain why a modelo does or does not apply to the active profile."""
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
