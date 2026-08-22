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
from typing import TYPE_CHECKING

import typer

from ...application import overview as _overview_application
from ...application.overview import (
    OverviewCalendar,
    OverviewCalendarEvent,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    build_overview_calendar,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import Notice, strict_round_trip
from ...core.logging import get_logger
from ...core.time import today_madrid
from ...domain.modelos import WorkUnit
from ._app_execution_policies import CALCULATION_READ, declare_metadata_group
from ._command_policy import command_execution_policy
from ._common import (
    _bad,
    _canonical_period,
    _declared_tax_id,
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
from ._overview_evidence import (
    _live_censo_verified_profile_keys,
    _local_calendar_filing_evidence,
    _local_live_calendar_events,
    _local_modelo_record_calendar_events,
    _local_modelo_work_units,
    overview_no_aeat_history_notice,
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
    overview_pipeline_output,
    overview_prepare_output,
    overview_status_output,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ...application.overview import CalendarWarning
    from ...application.user_profile import ProfileRecordRepository
    from ...application.workflow import ProfileBucketPointer as _ProfileBucketPointer
    from ...application.workflow import WorkflowState
    from ...domain.deadlines import TaxpayerProfile
    from ._errors import CliRefusedBoundaryError

logger = get_logger(__name__)

app = typer.Typer(
    name="overview",
    help=tr("cli.overview.app_help"),
    no_args_is_help=True,
)
declare_metadata_group(app)


def _grounded_warning_summary(warnings: Sequence[CalendarWarning]) -> str:
    """Render calendar warnings as grounded profile requirements where possible.

    A completeness warning's ``code`` is the profile field's declared selector
    token, so the schema resolves it to the field's operator label and the
    registry supplies its legal grounding - the same two facts the modelo work
    readiness gate names when it refuses for the same missing field.

    The warning stream also carries codes that are not profile fields at all
    (censo enrolment, unverified justificante, AEAT evidence conflict). Those
    resolve to nothing and pass through verbatim, which is what this surface
    already showed for them.
    """
    from ...application.user_profile import format_profile_selector_requirements
    from ...core.resources import resources
    from ...domain.calculations.registry import build_profile_grounding_index

    return ", ".join(
        format_profile_selector_requirements(
            (warning.code for warning in warnings),
            schema=resources().user_profile_schema.singleton,
            grounding_index=build_profile_grounding_index(resources().modelos.authority),
        ),
    )


def _incomplete_profile_refusal(warnings: Sequence[CalendarWarning]) -> CliRefusedBoundaryError:
    """Return the refusal for a projection blocked by unanswered profile facts.

    A profile fact the operator has not supplied is a workflow-state refusal,
    not invalid operator input, so it is raised as a refusal rather than as a
    parameter error: nothing the operator typed on this command line is wrong.

    Calendar warnings may describe several independent authorities.  Their
    aggregate does not bind one executable recovery action, so the refusal
    carries a typed no-recovery outcome rather than selecting one warning's
    command string.
    """
    from ...application.cli_exception_preconditions import (
        CliExceptionPrecondition,
        cli_exception_no_recovery_verdict,
    )
    from ._common import attach_cli_policy_verdict
    from ._errors import CliRefusedBoundaryError

    return attach_cli_policy_verdict(
        CliRefusedBoundaryError(
            translated_message="cli.overview.refused_incomplete_profile",
            context={"requirements": _grounded_warning_summary(warnings)},
        ),
        verdict=cli_exception_no_recovery_verdict(
            CliExceptionPrecondition.OVERVIEW_PROFILE_COMPLETE,
            facts={"warning_count": len(warnings)},
        ),
    )


#: The profile facts that together declare a taxpayer model, held as their
#: declared selector tokens. A natural person additionally needs at least one
#: IRPF income category; a legal or attribution entity is declared by its
#: entity type alone, so the second token is conditional.
_ENTITY_TYPE_SELECTOR = "taxpayer.entity_type"
_IRPF_INCOME_CATEGORIES_SELECTOR = "taxpayer.irpf_income_categories"


def _undeclared_taxpayer_model_refusal(profile: TaxpayerProfile) -> CliRefusedBoundaryError:
    """Return the refusal for a projection blocked by an undeclared taxpayer model.

    Applicability cannot be derived without an entity type, and for a natural
    person without at least one IRPF income category, so the engine reports
    incomplete rather than guessing autónomo. This names WHICH of those two
    facts is absent instead of stating only that the model is undeclared.

    Only the genuinely absent facts are named: a natural person who declared
    an entity type but no income category is told about the income category,
    not sent back to a field they already filled in.
    """
    from ...application.cli_exception_preconditions import (
        CliExceptionPrecondition,
        cli_exception_no_recovery_verdict,
    )
    from ...application.user_profile import format_profile_selector_requirements
    from ...core.resources import resources
    from ...domain.calculations.registry import build_profile_grounding_index
    from ...domain.deadlines import EntityType
    from ._common import attach_cli_policy_verdict
    from ._errors import CliRefusedBoundaryError

    missing: list[str] = []
    if profile.entity_type is None:
        missing.append(_ENTITY_TYPE_SELECTOR)
    elif profile.entity_type is EntityType.NATURAL_PERSON and not profile.irpf_income_categories:
        missing.append(_IRPF_INCOME_CATEGORIES_SELECTOR)
    return attach_cli_policy_verdict(
        CliRefusedBoundaryError(
            translated_message="cli.overview.refused_undeclared_taxpayer_model",
            context={
                "requirements": ", ".join(
                    format_profile_selector_requirements(
                        missing,
                        schema=resources().user_profile_schema.singleton,
                        grounding_index=build_profile_grounding_index(resources().modelos.authority),
                    ),
                ),
            },
        ),
        verdict=cli_exception_no_recovery_verdict(
            CliExceptionPrecondition.OVERVIEW_PROFILE_COMPLETE,
            facts={"missing_selector_count": len(missing)},
        ),
    )


def _refuse_calendar_warnings(cal: OverviewCalendar) -> None:
    raise _incomplete_profile_refusal(cal.warnings)


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


def _emit_period_overview_status(
    ctx: typer.Context,
    *,
    current: WorkflowState,
    period: str,
    year: int | None,
    verbose: bool,
) -> None:
    """Emit the typed draft projection for one canonical filing period."""
    drafts = _load_drafts()
    canonical = _overview_status_period(period, year=year)
    wanted = (canonical.filing_year, canonical.registry_token)

    def _draft_matches(draft_period: object) -> bool:
        # Drafts persist typed periods; compare their separate filing-year and
        # registry-token fields to the operator's ``--year``/``--period`` pair.
        filing_year = getattr(draft_period, "filing_year", None)
        registry_token = getattr(draft_period, "registry_token", None)
        return (
            isinstance(filing_year, int)
            and filing_year == wanted[0]
            and isinstance(registry_token, str)
            and registry_token == wanted[1]
        )

    per_modelo_drafts = [d for d in drafts if _draft_matches(d.period)]
    from ._overview_payloads import OverviewDraftPayload

    period_display = str(canonical)
    typed_period = OverviewStatusResult(
        period=period_display,
        drafts=[
            OverviewDraftPayload(draft_id=d.draft_id, modelo=d.modelo, status=d.status.value) for d in per_modelo_drafts
        ],
        verbose=verbose,
    )
    period_lines = [
        f"{tr('cli.overview.period')}\t{period_display}",
        f"{tr('cli.overview.drafts')}\t{len(per_modelo_drafts)}",
        *(f"{d.modelo}\t{d.draft_id}\t{d.status.value}" for d in per_modelo_drafts),
    ]
    _emit_envelope(ctx, command="overview.status", result=typed_period, lines=period_lines)


def _overview_status_coverage(
    current: WorkflowState | None,
    *,
    raw_values: Mapping[str, object] | None,
) -> tuple[list[str], list[Notice]]:
    """Build the obligation-coverage lines and notices for status output."""
    if current is None or current.active_profile_bucket_id() is None:
        return [], []

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
    coverage_lines: list[str] = []
    status_notices: list[Notice] = []
    for notice in overview_coverage_notices(status_cal.coverage):
        status_notices.append(notice)
        coverage_lines.append(f"coverage_advised\t{len(status_cal.coverage.advised)}\t{notice.message}")

    from ...domain.calculations.registry import derive_tax_route

    history_notice = overview_no_aeat_history_notice(
        tax_route=derive_tax_route(_profile_to_taxpayer(current)),
    )
    if history_notice is not None:
        status_notices.append(history_notice)
    return coverage_lines, status_notices


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
        _emit_period_overview_status(ctx, current=current, period=period, year=year, verbose=verbose)
        return
    profile_record = current.active_profile_record() if current is not None else None
    raw_values = record_to_values(profile_record) if profile_record is not None else None
    report = _overview_application.build_overview_status_report(state=current, raw_values=raw_values)
    typed_status = strict_round_trip(OverviewStatusResult, report)
    status_lines, status_notices = overview_status_output(report)
    # ``status`` is a "what must I file" surface too: reconcile the active
    # profile's obligation coverage over the current year and surface the same
    # default advisory the calendar does, so status never reads as complete while
    # obligations go unscoped. The coverage report rides the Notice channel.
    coverage_lines, coverage_notices = _overview_status_coverage(current, raw_values=raw_values)
    _emit_envelope(
        ctx,
        command="overview.status",
        result=typed_status,
        lines=[*status_lines, *coverage_lines],
        notices=[*status_notices, *coverage_notices],
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
    # The evidence matchers compare the operator's NIF against the authenticated
    # identity on each filed artefact, and every one of them fails OPEN on an
    # empty expected value and CLOSED on a non-empty mismatching one. The
    # taxpayer projection substitutes a synthetic placeholder NIF for an absent
    # identity, which is non-empty and matches nothing real, so feeding it here
    # inverts that design: an operator who has not yet declared a NIF would have
    # every genuinely filed obligation silently dropped and redisplayed as
    # unfiled. Read the declared identity instead, so absence stays absence.
    expected_tax_id = _declared_tax_id(record)
    evidence_notices: list[Notice] = []
    calendar_today = today_madrid()
    live_events, live_notice = _local_live_calendar_events(
        bucket_id,
        rng,
        as_of=calendar_today,
        expected_tax_id=expected_tax_id,
    )
    modelo_record_events, modelo_events_notice = _local_modelo_record_calendar_events(
        bucket_id,
        rng,
        expected_tax_id=expected_tax_id,
    )
    events = (*live_events, *modelo_record_events)
    filing_evidence, filing_evidence_notice = _local_calendar_filing_evidence(
        bucket_id,
        events,
        expected_tax_id=expected_tax_id,
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
        today=calendar_today,
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
        raise _undeclared_taxpayer_model_refusal(_profile_to_taxpayer(current))
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


@dataclass(frozen=True)
class _ProfileCalendarInputs:
    """Everything one profile's calendar is built from, read in one session.

    Carries the profile's :class:`TaxpayerProfile` snapshot alongside its
    calendar events, filing evidence, and work units.
    """

    taxpayer: TaxpayerProfile
    raw_values: Mapping[str, object]
    events: tuple[OverviewCalendarEvent, ...]
    filing_evidence: tuple[OverviewCalendarFilingEvidence, ...]
    work_units: tuple[WorkUnit, ...]
    live_censo_verified_profile_keys: tuple[str, ...] | None


def _profile_calendar_inputs(
    repository: ProfileRecordRepository,
    bucket_id: str,
    *,
    rng: OverviewCalendarRange,
    as_of: _date,
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
    from ...application.user_profile import projection_for_taxpayer, record_to_values

    try:
        record = repository.load(bucket_id)
        taxpayer = projection_for_taxpayer(record)
        live_events, _ = _local_live_calendar_events(
            bucket_id,
            rng,
            as_of=as_of,
            expected_tax_id=taxpayer.tax_id,
        )
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
            raw_values=record_to_values(record),
            events=events,
            filing_evidence=filing_evidence,
            work_units=work_units,
            live_censo_verified_profile_keys=_live_censo_verified_profile_keys(record),
        )
    except typer.BadParameter:
        raise
    except Exception:
        logger.warning("overview calendar: skipping unreadable profile %s (%s)", bucket_id, label, exc_info=True)
        return None


def _calendar_profile_groups(
    buckets: Mapping[str, _ProfileBucketPointer],
    *,
    active_bucket_id: str | None,
) -> tuple[dict[str, _ProfileBucketPointer], list[_ProfileBucketPointer], list[_ProfileBucketPointer]]:
    """Classify registered profiles without treating labels as readiness authority."""
    from ...application.user_profile import ProfileRecordRepository
    from ...domain.user_profile import ProfileNotFoundError, ProfileSetupState

    active: dict[str, _ProfileBucketPointer] = {}
    setup_incomplete: list[_ProfileBucketPointer] = []
    locked: list[_ProfileBucketPointer] = []
    for bucket_id, pointer in buckets.items():
        if bucket_id != active_bucket_id:
            locked.append(pointer)
            continue
        try:
            record = ProfileRecordRepository.for_current_session(bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            locked.append(pointer)
            continue
        if record.setup_state is ProfileSetupState.COMPLETE:
            active[bucket_id] = pointer
        else:
            setup_incomplete.append(pointer)
    setup_incomplete.sort(key=lambda pointer: pointer.label)
    locked.sort(key=lambda pointer: pointer.label)
    return active, setup_incomplete, locked


def _profile_calendar_projection(
    bucket_id: str,
    pointer: _ProfileBucketPointer,
    *,
    rng: OverviewCalendarRange,
    as_of: _date,
    allow_incomplete: bool,
    show_suppressed: bool,
) -> tuple[dict[str, object], list[str], list[Notice]] | None:
    """Build one profile calendar block, or return ``None`` for a skipped bucket."""
    from ...application.user_profile import ProfileRecordRepository

    inputs = _profile_calendar_inputs(
        ProfileRecordRepository.for_current_session(bucket_id),
        bucket_id,
        rng=rng,
        as_of=as_of,
        label=pointer.label,
    )
    if inputs is None:
        return None
    cal = build_overview_calendar(
        inputs.taxpayer,
        rng,
        today=as_of,
        raw_values=inputs.raw_values,
        show_suppressed=show_suppressed,
        events=inputs.events,
        filing_evidence=inputs.filing_evidence,
        work_units=inputs.work_units,
        live_censo_verified_profile_keys=inputs.live_censo_verified_profile_keys,
    )
    if cal.warnings and not allow_incomplete:
        _refuse_calendar_warnings(cal)
    return overview_calendar_profile_output(bucket_id=bucket_id, label=pointer.label, cal=cal)


def _overview_calendar_all_profiles(
    ctx: typer.Context,
    *,
    rng: OverviewCalendarRange,
    allow_incomplete: bool,
    show_suppressed: bool,
) -> None:
    """Emit the deadline calendar for every registered active profile.

    Iterates :func:`list_profile_buckets` and reads only the already
    authenticated active capsule. Other profiles remain locked projections.
    The combined JSON payload uses the single
    :class:`OverviewCalendarResult` schema registered for
    ``overview.calendar``.
    """
    from ...application.workflow import list_profile_buckets
    from ...core import resolve_active_bucket_id

    today = today_madrid()
    buckets = list_profile_buckets()
    active_buckets, setup_incomplete, locked = _calendar_profile_groups(
        buckets,
        active_bucket_id=resolve_active_bucket_id(),
    )

    all_lines: list[str] = [
        f"from\t{rng.from_date.isoformat()}",
        f"to\t{rng.to_date.isoformat()}",
        f"profiles\t{len(active_buckets)}",
    ]
    all_lines.extend(f"profile_locked\t{pointer.bucket_id}\t{pointer.label}" for pointer in locked)
    all_lines.extend(f"profile_setup_incomplete\t{pointer.bucket_id}\t{pointer.label}" for pointer in setup_incomplete)
    all_coverage_notices: list[Notice] = []
    all_calendars: list[dict[str, object]] = []

    for bucket_id, pointer in sorted(active_buckets.items(), key=lambda kv: kv[1].label):
        projection = _profile_calendar_projection(
            bucket_id,
            pointer,
            rng=rng,
            as_of=today,
            allow_incomplete=allow_incomplete,
            show_suppressed=show_suppressed,
        )
        if projection is None:
            all_lines.append(f"profile_skipped\t{bucket_id}\t{pointer.label}")
            continue
        profile_payload, profile_lines, profile_notices = projection
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
        raise _undeclared_taxpayer_model_refusal(_profile_to_taxpayer(current))
    if agenda.warnings and not allow_incomplete:
        raise _incomplete_profile_refusal(agenda.warnings)

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
        raise _undeclared_taxpayer_model_refusal(_profile_to_taxpayer(current))
    if backlog.warnings and not allow_incomplete:
        raise _incomplete_profile_refusal(backlog.warnings)

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
        ledger=strict_round_trip(LedgerStatusResult, report.ledger),
    )
    _emit_envelope(ctx, command="overview.pipeline", result=typed_result, lines=lines, notices=notices)


for _callback in (
    overview_status,
    overview_calendar,
    overview_agenda,
    overview_backlog,
    overview_explain,
    overview_prepare,
    overview_pipeline,
):
    command_execution_policy(CALCULATION_READ)(_callback)
