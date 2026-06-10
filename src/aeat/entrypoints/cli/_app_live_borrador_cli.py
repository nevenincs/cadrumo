"""Typer registration for live Modelo 100 borrador snapshot commands."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Annotated, TypedDict

import typer

from ...application.live import Borrador100SnapshotService, SnapshotLifecycleState
from ...core.i18n import tr
from ._app_live_payloads import (
    Borrador100LatestResult,
    Borrador100ListResult,
    Borrador100SnapshotSummaryPayload,
    Borrador100ViewResult,
)
from ._common import _emit_envelope


class _BorradorRow(TypedDict):
    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: str


borrador_app = typer.Typer(
    name="borrador",
    help=tr("cli.app.live.borrador.app_help", default="Modelo 100 borrador snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
borrador_100_app = typer.Typer(
    name="100",
    help=tr("cli.app.live.borrador.modelo_100_help", default="Modelo 100 borrador subgroup."),
    no_args_is_help=True,
    add_completion=False,
)
borrador_app.add_typer(borrador_100_app, name="100")


def register_borrador_commands(app: typer.Typer, *, active_bucket_id: Callable[[], str]) -> None:
    """Mount the live borrador subgroup and register its read-only commands."""
    app.add_typer(borrador_app, name="borrador")

    @borrador_100_app.command(
        "list",
        help=tr(
            "cli.app.live.borrador.list_help",
            default="List persisted Modelo 100 borrador snapshots.",
        ),
    )
    def borrador_100_list(
        ctx: typer.Context,
        state: Annotated[
            str,
            typer.Option(
                "--state",
                help=tr(
                    "cli.app.live.borrador.state_help",
                    default="Snapshot state filter: active, superseded, discarded, or all.",
                ),
            ),
        ] = "active",
    ) -> None:
        """List persisted Modelo 100 borrador snapshots for the active bucket."""
        bucket_id = active_bucket_id()
        try:
            state_filter = None if state == "all" else SnapshotLifecycleState(state)
        except ValueError as exc:
            raise typer.BadParameter(tr("cli.app.live.borrador.invalid_state")) from exc
        rows = Borrador100SnapshotService(bucket_id=bucket_id).list_snapshots(state=state_filter)
        result = Borrador100ListResult(
            bucket_id=bucket_id,
            count=len(rows),
            rows=[Borrador100SnapshotSummaryPayload(**_borrador_row(row)) for row in rows],
        )
        lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
        for row in rows:
            lines.append(
                f"{row.snapshot_id}\t{row.filing_year}\t{row.period}\t{row.captured_at.isoformat()}\t"
                f"bindings={len(row.binding_values)}\t{row.state.value}"
            )
        _emit_envelope(ctx, command="app.live.borrador.100.list", result=result, lines=lines)

    @borrador_100_app.command(
        "view",
        help=tr(
            "cli.app.live.borrador.view_help",
            default="View one Modelo 100 borrador snapshot.",
        ),
    )
    def borrador_100_show(
        ctx: typer.Context,
        snapshot_id: Annotated[
            str,
            typer.Argument(
                help=tr(
                    "cli.app.live.borrador.snapshot_id_help",
                    default="Snapshot id (or unambiguous prefix).",
                ),
            ),
        ],
    ) -> None:
        """Show one Modelo 100 borrador snapshot with its casilla binding values."""
        bucket_id = active_bucket_id()
        record = Borrador100SnapshotService(bucket_id=bucket_id).show(snapshot_id)
        binding_values = {
            key: format(value, "f") if isinstance(value, Decimal) else str(value)
            for key, value in record.binding_values.items()
        }
        result = Borrador100ViewResult(
            bucket_id=bucket_id,
            **_borrador_row(record),
            binding_values=binding_values,
        )
        lines = [
            f"bucket\t{bucket_id}",
            f"snapshot_id\t{record.snapshot_id}",
            f"filing_year\t{record.filing_year}",
            f"period\t{record.period}",
            f"captured_at\t{record.captured_at.isoformat()}",
            f"source_url\t{record.source_url}",
            f"binding_count\t{len(record.binding_values)}",
            f"state\t{record.state.value}",
        ]
        _emit_envelope(ctx, command="app.live.borrador.100.view", result=result, lines=lines)

    @borrador_100_app.command(
        "latest",
        help=tr(
            "cli.app.live.borrador.latest_help",
            default="Show the most recent active snapshot for a filing year.",
        ),
    )
    def borrador_100_latest(
        ctx: typer.Context,
        filing_year: Annotated[
            int,
            typer.Option(
                "--filing-year",
                min=2000,
                max=2099,
                help=tr("cli.app.live.borrador.filing_year_help", default="Filing year (e.g. 2024)."),
            ),
        ],
    ) -> None:
        """Show the most recent active Modelo 100 borrador snapshot for the given filing year."""
        bucket_id = active_bucket_id()
        record = Borrador100SnapshotService(bucket_id=bucket_id).latest_for_year(filing_year=filing_year)
        if record is None:
            result = Borrador100LatestResult(bucket_id=bucket_id, filing_year=filing_year, snapshot_id=None)
            _emit_envelope(
                ctx,
                command="app.live.borrador.100.latest",
                result=result,
                lines=[f"bucket\t{bucket_id}", f"filing_year\t{filing_year}", "snapshot_id\t-"],
            )
            return
        result = Borrador100LatestResult(
            bucket_id=bucket_id,
            filing_year=record.filing_year,
            snapshot_id=record.snapshot_id,
            captured_at=record.captured_at.isoformat(),
            period=record.period,
            source_url=record.source_url,
            binding_count=len(record.binding_values),
            state=record.state.value,
        )
        lines = [
            f"bucket\t{bucket_id}",
            f"snapshot_id\t{record.snapshot_id}",
            f"filing_year\t{record.filing_year}",
            f"period\t{record.period}",
            f"captured_at\t{record.captured_at.isoformat()}",
            f"binding_count\t{len(record.binding_values)}",
        ]
        _emit_envelope(ctx, command="app.live.borrador.100.latest", result=result, lines=lines)


def _borrador_row(snapshot) -> _BorradorRow:
    return _BorradorRow(
        snapshot_id=snapshot.snapshot_id,
        filing_year=snapshot.filing_year,
        period=snapshot.period,
        captured_at=snapshot.captured_at.isoformat(),
        source_url=snapshot.source_url,
        binding_count=len(snapshot.binding_values),
        state=snapshot.state.value,
    )


__all__ = ["borrador_100_app", "borrador_app", "register_borrador_commands"]
