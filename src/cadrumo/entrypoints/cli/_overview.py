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
:func:`~cadrumo.application.overview.build_data_prep_walkthrough`, and
:func:`~cadrumo.application.overview.build_pipeline_health_report`. Each command
emits a typed payload such as :class:`OverviewStatusResult`,
:class:`OverviewCalendarResult`, :class:`OverviewAgendaResult`,
:class:`OverviewBacklogResult`, :class:`OverviewExplainResult`,
:class:`OverviewPrepareResult`, or :class:`OverviewPipelineResult` through
:func:`_emit_envelope`. The ``pipeline`` verb resolves each period work
unit's current :class:`~cadrumo.domain.modelos.CalculationRevision` to derive its
readiness row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from ...application import overview as _overview_application
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
from ...core.time import today_madrid
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
    OverviewCalendarResult,
    OverviewStatusResult,
)
from ._overview_rendering import (
    _calendar_shift_reason_text as _calendar_shift_reason_text,
)
from ._overview_rendering import (
    overview_agenda_output,
    overview_backlog_output,
    overview_calendar_output,
    overview_calendar_profile_output,
    overview_coverage_notices,
    overview_explain_output,
    overview_next_step_notices,
    overview_pipeline_output,
    overview_prepare_output,
    render_cli_overview_status_lines,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ...application.user_profile import ProfileRepository
    from ...application.workflow import ProfileBucketPointer as _ProfileBucketPointer
    from ...domain.deadlines import TaxpayerProfile

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
    from ...application.user_profile import CENSO_SOURCE_TAG

    verified_sources = {CENSO_SOURCE_TAG}
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
        filed_observation_store = FiledDeclaracionObservationStore(Path("var/cadrumo/filed-declarations"))
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
    is now the first-class `aeat app overview calendar` verb. No alternate
    flag path remains; callers must use the dedicated verb. The full-status branch projects
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
        wanted = (canonical.filing_year, canonical.registry_token)

        def _draft_matches(draft_period: object) -> bool:
            # Drafts persist typed periods; compare their separate filing-year
            # and registry-token fields to the operator's ``--year``/``--period`` pair.
            return (
                getattr(draft_period, "filing_year", None) == wanted[0]
                and getattr(draft_period, "registry_token", None) == wanted[1]
            )

        per_modelo_drafts = [d for d in drafts if _draft_matches(d.period)]
        from ._overview_payloads import OverviewDraftPayload

        period_display = str(canonical)
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
        status_today = today_madrid()
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
        raise _no_active_profile_refusal()
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
        today=today_madrid(),
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
    typed_cal, lines, calendar_notices = overview_calendar_output(
        cal,
        rng,
        evidence_notices=evidence_notices,
    )
    _emit_envelope(
        ctx,
        command="overview.calendar",
        result=typed_cal,
        lines=lines,
        notices=calendar_notices,
    )


def _setup_incomplete_disclosure(
    setup_incomplete: Sequence[_ProfileBucketPointer],
) -> tuple[list[str], list[Notice]]:
    """Name every setup-incomplete profile the multi-profile view cannot render.

    Such a profile is not workable, so it has no filing calendar — but it
    must not vanish silently from the view. Each is named on a stable
    machine line, and one non-blocking advisory rides the typed Notice
    channel.
    """
    lines = [f"profile_setup_incomplete\t{pointer.bucket_id}\t{pointer.label}" for pointer in setup_incomplete]
    if not setup_incomplete:
        return lines, []
    labels = ", ".join(pointer.label for pointer in setup_incomplete)
    notice = Notice(
        severity=NoticeSeverity.INFO,
        code="overview.calendar.setup_incomplete",
        message=tr("cli.overview.calendar.setup_incomplete_notice", count=len(setup_incomplete), labels=labels),
        suggestion="aeat config profile status",
        context={"count": str(len(setup_incomplete)), "labels": labels},
    )
    return lines, [notice]


@dataclass(frozen=True)
class _ProfileCalendarInputs:
    """Everything one profile's calendar is built from, read in one session."""

    taxpayer: TaxpayerProfile
    raw_values: Mapping[str, object]
    events: tuple[OverviewCalendarEvent, ...]
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...]
    work_units: tuple[WorkUnit, ...]
    live_censo_verified_profile_keys: tuple[str, ...] | None


def _profile_calendar_inputs(
    repository: ProfileRepository,
    bucket_id: str,
    *,
    rng: OverviewCalendarRange,
    label: str,
) -> _ProfileCalendarInputs | None:
    """Read one profile's calendar inputs, or ``None`` when the bucket is unreadable.

    An unreadable bucket is skipped with a warning rather than aborting the
    scan, so one damaged profile does not deny every other profile its
    calendar. The per-loader degradation notices are dropped here: the
    multi-profile view already degrades per profile and renders many
    calendars in one payload, and each loader still returns schedule-only
    evidence rather than raising.
    """
    from ...application.user_profile import (
        profile_storage_session,
        projection_for_taxpayer,
        record_to_values,
    )

    try:
        with profile_storage_session(bucket_id):
            record = repository.load(bucket_id)
            taxpayer = projection_for_taxpayer(record.record, tax_id_default="00000000T")
            live_events, _ = _local_live_calendar_events(bucket_id, rng, expected_tax_id=taxpayer.tax_id)
            modelo_record_events, _ = _local_modelo_record_calendar_events(
                bucket_id,
                rng,
                expected_tax_id=taxpayer.tax_id,
            )
            events = (*live_events, *modelo_record_events)
            filing_evidence, _ = _local_calendar_filing_evidence(bucket_id, events, expected_tax_id=taxpayer.tax_id)
            work_units, _ = _local_modelo_work_units(bucket_id)
            return _ProfileCalendarInputs(
                taxpayer=taxpayer,
                raw_values=record_to_values(record.record),
                events=events,
                filing_evidence=filing_evidence,
                work_units=work_units,
                live_censo_verified_profile_keys=_live_censo_verified_profile_keys(record.record),
            )
    except typer.BadParameter:
        raise
    except Exception:
        logger.warning("overview calendar: skipping unreadable profile %s (%s)", bucket_id, label, exc_info=True)
        return None


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
    from ...application.user_profile import (
        ProfileRepository,
    )
    from ...application.workflow import list_profile_buckets
    from ...domain.user_profile import UserProfileStatus

    today = today_madrid()
    buckets = list_profile_buckets()
    active_buckets = {bid: ptr for bid, ptr in buckets.items() if ptr.status is UserProfileStatus.ACTIVE}
    setup_incomplete = sorted(
        (ptr for ptr in buckets.values() if ptr.status is UserProfileStatus.SETUP_INCOMPLETE),
        key=lambda ptr: ptr.label,
    )

    all_lines: list[str] = [
        f"from\t{rng.from_date.isoformat()}",
        f"to\t{rng.to_date.isoformat()}",
        f"profiles\t{len(active_buckets)}",
    ]
    # A setup-incomplete profile is not workable, so it has no filing
    # calendar — but it must not vanish silently from the multi-profile view.
    # Name each excluded profile on a stable machine line and surface one
    # non-blocking advisory on the typed Notice channel.
    incomplete_lines, all_coverage_notices = _setup_incomplete_disclosure(setup_incomplete)
    all_lines.extend(incomplete_lines)
    all_calendars: list[dict[str, object]] = []

    repository = ProfileRepository()
    for bucket_id, pointer in sorted(active_buckets.items(), key=lambda kv: kv[1].label):
        inputs = _profile_calendar_inputs(repository, bucket_id, rng=rng, label=pointer.label)
        if inputs is None:
            all_lines.append(f"profile_skipped\t{bucket_id}\t{pointer.label}")
            continue

        cal = build_overview_calendar(
            inputs.taxpayer,
            rng,
            today=today,
            raw_values=inputs.raw_values,
            show_suppressed=show_suppressed,
            events=inputs.events,
            filing_evidence=inputs.filing_evidence,
            work_units=inputs.work_units,
            live_censo_verified_profile_keys=inputs.live_censo_verified_profile_keys,
        )

        if cal.warnings and not allow_incomplete:
            _refuse_calendar_warnings(cal)
        profile_payload, profile_lines, profile_notices = overview_calendar_profile_output(
            bucket_id=bucket_id,
            label=pointer.label,
            cal=cal,
        )
        all_lines.extend(profile_lines)
        all_coverage_notices.extend(profile_notices)
        all_calendars.append(profile_payload)

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
    as_of_date = _parse_iso_date(as_of, label="--date") if as_of else today_madrid()
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

    typed_agenda, lines, coverage_notices = overview_agenda_output(agenda)
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
        raise _no_active_profile_refusal()
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

    typed_backlog, lines, backlog_notices = overview_backlog_output(
        backlog,
        work_units_notice=work_units_notice,
    )
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
    typed_explain, lines = overview_explain_output(result)
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
    :func:`~cadrumo.application.overview.build_data_prep_walkthrough`; this
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

    typed_result, lines, notices = overview_prepare_output(walkthrough)
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
    :func:`~cadrumo.application.overview.build_pipeline_health_report`; this
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
    from ...application.overview import build_pipeline_health_report
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

    typed_result, lines, notices = overview_pipeline_output(
        report,
        ledger=LedgerStatusResult.model_validate(report.ledger.model_dump(mode="json")),
    )
    _emit_envelope(ctx, command="overview.pipeline", result=typed_result, lines=lines, notices=notices)
