from __future__ import annotations

from datetime import date as _date

import typer

from ...application.diagnostics import secure_object_unreadable_total
from ...application.overview import (
    OverviewCalendar,
    OverviewCalendarRange,
    build_overview_calendar,
)
from ._common import (
    _bad,
    _canonical_period,
    _emit,
    _load_drafts,
    _load_invoices,
    _load_transactions,
    _parse_iso_date,
    _profile_to_autonomo,
    _state,
)
from ._i18n import tr

app = typer.Typer(
    name="overview",
    help=tr("cli.overview.app_help"),
    no_args_is_help=True,
)


@app.command("status", help=tr("cli.overview.status_help"))
def overview_status(
    ctx: typer.Context,
    calendar: bool = typer.Option(False, "--calendar", help=tr("cli.overview.calendar_help")),
    period: str | None = typer.Option(None, "--period", help=tr("cli.overview.period_help")),
    from_date: str | None = typer.Option(None, "--from", help=tr("cli.overview.from_help")),
    to_date: str | None = typer.Option(None, "--to", help=tr("cli.overview.to_help")),
    verbose: bool = typer.Option(False, "--verbose", help=tr("cli.overview.verbose_help")),
    allow_incomplete: bool = typer.Option(
        False,
        "--allow-incomplete",
        help=tr("cli.overview.allow_incomplete_help"),
    ),
) -> None:
    """Render workspace state, calendar view, or per-period detail."""
    current = _state()
    transactions = _load_transactions()
    invoices = _load_invoices()
    drafts = _load_drafts()
    if calendar:
        if not from_date or not to_date:
            raise _bad(tr("cli.overview.calendar_requires_dates"))
        rng = OverviewCalendarRange(
            from_date=_parse_iso_date(from_date, label="--from"),
            to_date=_parse_iso_date(to_date, label="--to"),
        )
        record = current.active_profile_record()
        raw_values = record.values if record is not None else None
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
                )
            )
        payload = {
            "calendar": cal,
            "transactions": len(transactions.transactions),
            "invoices": len(invoices),
            "drafts": len(drafts),
        }
        lines: list[str] = [tr("cli.overview.header")]
        lines.extend(
            f"{entry.modelo}\t{entry.period}\t{entry.user_state.value}\t{entry.opens_on.isoformat()}\t{entry.closes_on.isoformat()}"
            for entry in cal.entries
        )
        for warning in cal.warnings:
            lines.append(f"warning\t{warning.code}\t{tr(warning.message)}\tfix={warning.fix_command}")
        if cal.completeness.computable_modelos:
            lines.append(
                f"computable\t{len(cal.completeness.computable_modelos)}\tdefaulted\t{len(cal.completeness.defaulted_modelos)}"
            )
        _emit(ctx, payload, lines)
        return
    if period is not None:
        canonical = _canonical_period(period)
        per_modelo_drafts = [d for d in drafts if d.period == canonical]
        payload = {
            "period": canonical,
            "drafts": [
                {"draft_id": d.draft_id, "modelo": d.modelo, "status": d.status.value} for d in per_modelo_drafts
            ],
            "verbose": verbose,
        }
        lines: list[str] = [
            f"{tr('cli.overview.period')}\t{canonical}",
            f"{tr('cli.overview.drafts')}\t{len(per_modelo_drafts)}",
        ]
        for d in per_modelo_drafts:
            lines.append(f"{d.modelo}\t{d.draft_id}\t{d.status.value}")
        _emit(ctx, payload, lines)
        return
    unreadable = secure_object_unreadable_total()
    payload = {
        "active_profile": current.active_profile,
        "transactions": len(transactions.transactions),
        "invoices": len(invoices),
        "drafts": len(drafts),
        "unreadable_rows": unreadable,
    }
    lines = [
        f"{tr('cli.overview.profile')}\t{current.active_profile or ''}",
        f"{tr('cli.overview.transactions')}\t{len(transactions.transactions)}",
        f"{tr('cli.overview.invoices')}\t{len(invoices)}",
        f"{tr('cli.overview.drafts')}\t{len(drafts)}",
    ]
    if unreadable > 0:
        lines.append(tr("cli.overview.integrity_warning", count=unreadable))
    _emit(ctx, payload, lines)
