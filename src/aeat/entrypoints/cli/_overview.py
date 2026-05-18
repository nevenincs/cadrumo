from __future__ import annotations

from datetime import date as _date

import typer

from ...application.overview import (
    OverviewCalendar,
    OverviewCalendarRange,
    build_overview_calendar,
    build_overview_status_report,
)
from ._common import (
    _bad,
    _canonical_period,
    _emit,
    _load_drafts,
    _parse_iso_date,
    _profile_to_autonomo,
    _state,
)
from ...core.i18n import tr
from ._overview_rendering import render_cli_overview_status_lines

app = typer.Typer(
    name="overview",
    help=tr("cli.overview.app_help"),
    no_args_is_help=True,
)


@app.command("status", help=tr("cli.overview.status_help"))
def overview_status(
    ctx: typer.Context,
    period: str | None = typer.Option(None, "--period", help=tr("cli.overview.period_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.overview.verbose_help")),
) -> None:
    """Render workspace readiness or per-period detail.

    The deadline-calendar surface that used to live behind `--calendar`
    is now the first-class `aeat app overview calendar` verb per the
    app-overview-shape ADR's Consequences section. No compatibility
    shim is preserved; callers must use the dedicated verb.
    """
    current = _state()
    if period is not None:
        drafts = _load_drafts()
        canonical = _canonical_period(period)
        per_modelo_drafts = [d for d in drafts if d.period == canonical]
        payload = {
            "period": canonical,
            "drafts": [
                {"draft_id": d.draft_id, "modelo": d.modelo, "status": d.status.value} for d in per_modelo_drafts
            ],
            "verbose": verbose,
        }
        period_lines: list[str] = [
            f"{tr('cli.overview.period')}\t{canonical}",
            f"{tr('cli.overview.drafts')}\t{len(per_modelo_drafts)}",
        ]
        for d in per_modelo_drafts:
            period_lines.append(f"{d.modelo}\t{d.draft_id}\t{d.status.value}")
        _emit(ctx, payload, period_lines)
        return
    report = build_overview_status_report(state=current)
    _emit(ctx, report, render_cli_overview_status_lines(report))


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
) -> None:
    """Render the deadline calendar over the supplied window."""

    from ...application.user_profile._projections import record_to_values

    current = _state()
    rng = OverviewCalendarRange(
        from_date=_parse_iso_date(from_date, label="--from"),
        to_date=_parse_iso_date(to_date, label="--to"),
    )
    record = current.active_profile_record()
    raw_values = record_to_values(record) if record is not None else None
    cal: OverviewCalendar = build_overview_calendar(
        _profile_to_autonomo(current),
        rng,
        today=_date.today(),
        raw_values=raw_values,
    )
    if cal.warnings and not allow_incomplete:
        warning_summary = ", ".join(warning.code for warning in cal.warnings)
        raise _bad(
            tr(
                "cli.overview.calendar_refused_incomplete",
                keys=warning_summary,
            ),
        )
    payload = cal.model_dump(mode="json")
    lines: list[str] = [
        f"from\t{rng.from_date.isoformat()}",
        f"to\t{rng.to_date.isoformat()}",
        f"entries\t{len(cal.entries)}",
    ]
    for entry in cal.entries:
        lines.append(
            f"{entry.modelo}\t{entry.period}\t{entry.user_state.value}"
            f"\topens={entry.opens_on.isoformat()}"
            f"\tcloses={entry.closes_on.isoformat()}"
            f"\tadjusted={entry.adjusted_closes_on.isoformat()}"
            f"\tshift={entry.shift_reason}"
        )
    for warning in cal.warnings:
        lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
    if cal.completeness.computable_modelos:
        lines.append(
            f"computable\t{len(cal.completeness.computable_modelos)}"
            f"\tdefaulted\t{len(cal.completeness.defaulted_modelos)}"
        )
    _emit(ctx, payload, lines)


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

    from ...application.overview._agenda import build_overview_agenda
    from ...application.user_profile._projections import record_to_values

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
        _profile_to_autonomo(current),
        as_of=as_of_date,
        horizon_days=horizon_days,
        raw_values=raw_values,
    )
    if agenda.warnings and not allow_incomplete:
        warning_summary = ", ".join(warning.code for warning in agenda.warnings)
        raise _bad(
            tr(
                "cli.overview.calendar_refused_incomplete",
                keys=warning_summary,
            ),
        )

    payload = agenda.model_dump(mode="json")
    lines: list[str] = [
        f"as_of\t{agenda.as_of.isoformat()}",
        f"horizon_days\t{agenda.horizon_days}",
    ]
    if agenda.next_due is not None:
        lines.append(
            f"next_due\t{agenda.next_due.modelo}\t{agenda.next_due.period}"
            f"\tcloses={agenda.next_due.adjusted_closes_on.isoformat()}"
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
    _emit(ctx, payload, lines)


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

    from ...application.overview._backlog import build_overview_backlog
    from ...application.user_profile._projections import record_to_values

    current = _state()
    parsed_from = _parse_iso_date(from_date, label="--from") if from_date else None
    parsed_to = _parse_iso_date(to_date, label="--to") if to_date else None
    record = current.active_profile_record()
    raw_values = record_to_values(record) if record is not None else None
    backlog = build_overview_backlog(
        _profile_to_autonomo(current),
        from_date=parsed_from,
        to_date=parsed_to,
        raw_values=raw_values,
    )
    if backlog.warnings and not allow_incomplete:
        warning_summary = ", ".join(warning.code for warning in backlog.warnings)
        raise _bad(
            tr(
                "cli.overview.calendar_refused_incomplete",
                keys=warning_summary,
            ),
        )

    payload = backlog.model_dump(mode="json")
    lines: list[str] = [
        f"from\t{backlog.range.from_date.isoformat()}",
        f"to\t{backlog.range.to_date.isoformat()}",
        f"as_of\t{backlog.as_of.isoformat()}",
        f"late_count\t{backlog.late_count}",
    ]
    for entry in backlog.items:
        lines.append(
            f"{entry.modelo}\t{entry.period}\tcloses={entry.adjusted_closes_on.isoformat()}"
        )
    for warning in backlog.warnings:
        lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
    _emit(ctx, payload, lines)


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

    from ...application.overview._errors import OverviewExplainError
    from ...application.overview._explain import build_overview_explain

    current = _state()
    try:
        result = build_overview_explain(
            _profile_to_autonomo(current),
            modelo=modelo,
            year=year,
        )
    except OverviewExplainError as exc:
        raise _bad(str(exc)) from exc
    payload = result.model_dump(mode="json")
    lines: list[str] = [
        f"modelo\t{result.modelo}",
        f"year\t{result.year}",
        f"applicable\t{str(result.applicable).lower()}",
        f"rationale\t{result.rationale}",
    ]
    for fact_name, fact_value in sorted(result.profile_facts.items()):
        lines.append(f"profile_fact\t{fact_name}\t{fact_value}")
    _emit(ctx, payload, lines)
