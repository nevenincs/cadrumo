from __future__ import annotations

from datetime import date as _date

import typer

from ...application.overview import (
    OverviewCalendar,
    OverviewCalendarRange,
    build_overview_calendar,
)
from ._v6_common import (
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

app = typer.Typer(
    name="overview",
    help="Profile-scoped readiness and period coverage.",
    no_args_is_help=True,
)


@app.command("status", help="Workspace readiness, optionally per-period or via a calendar window.")
def overview_status(
    ctx: typer.Context,
    calendar: bool = typer.Option(False, "--calendar", help="Render a per-period calendar table."),
    period: str | None = typer.Option(None, "--period", help="Show one canonical period."),
    from_date: str | None = typer.Option(None, "--from", help="Calendar window start (ISO date)."),
    to_date: str | None = typer.Option(None, "--to", help="Calendar window end (ISO date)."),
    verbose: bool = typer.Option(False, "--verbose", help="Show extra diagnostic detail."),
) -> None:
    """Render workspace state, calendar view, or per-period detail."""
    current = _state()
    transactions = _load_transactions()
    invoices = _load_invoices()
    drafts = _load_drafts()
    if calendar:
        if not from_date or not to_date:
            raise _bad("--calendar requires --from DATE and --to DATE")
        rng = OverviewCalendarRange(
            from_date=_parse_iso_date(from_date, label="--from"),
            to_date=_parse_iso_date(to_date, label="--to"),
        )
        cal: OverviewCalendar = build_overview_calendar(_profile_to_autonomo(current), rng, today=_date.today())
        payload = {
            "calendar": cal,
            "transactions": len(transactions.transactions),
            "invoices": len(invoices),
            "drafts": len(drafts),
        }
        lines: list[str] = ["modelo\tperiod\tstate\topens\tcloses"]
        lines.extend(
            f"{entry.modelo}\t{entry.period}\t{entry.user_state.value}\t{entry.opens_on.isoformat()}\t{entry.closes_on.isoformat()}"
            for entry in cal.entries
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
        lines: list[str] = [f"period\t{canonical}", f"drafts\t{len(per_modelo_drafts)}"]
        for d in per_modelo_drafts:
            lines.append(f"{d.modelo}\t{d.draft_id}\t{d.status.value}")
        _emit(ctx, payload, lines)
        return
    payload = {
        "active_profile": current.active_profile,
        "transactions": len(transactions.transactions),
        "invoices": len(invoices),
        "drafts": len(drafts),
    }
    _emit(
        ctx,
        payload,
        [
            f"profile\t{current.active_profile or ''}",
            f"transactions\t{len(transactions.transactions)}",
            f"invoices\t{len(invoices)}",
            f"drafts\t{len(drafts)}",
        ],
    )
