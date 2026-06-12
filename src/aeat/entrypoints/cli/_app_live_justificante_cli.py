"""Typer registration for live justificante-capture commands."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated

import typer

from ...core import Period, PeriodError
from ...core.i18n import tr
from ._common import _emit_envelope

_active_bucket_id: Callable[[], str] | None = None
_auth_preflight: Callable[[], None] | None = None

justificante_app = typer.Typer(
    name="justificante",
    help=tr(
        "cli.app.live.justificante.app_help",
        default="AEAT justificante captures (read-only): pull a filed receipt and reconcile against it.",
    ),
    no_args_is_help=True,
    add_completion=False,
)


def register_justificante_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
    auth_preflight: Callable[[], None],
) -> None:
    """Mount live justificante commands on the live app."""
    global _active_bucket_id, _auth_preflight
    _active_bucket_id = active_bucket_id
    _auth_preflight = auth_preflight
    app.add_typer(justificante_app, name="justificante")


def _bucket_id() -> str:
    if _active_bucket_id is None:
        raise RuntimeError("live justificante commands were not registered")
    return _active_bucket_id()


def _run_auth_preflight() -> None:
    if _auth_preflight is None:
        raise RuntimeError("live justificante commands were not registered")
    _auth_preflight()


def _period_option(period: str, *, year: int) -> Period:
    try:
        return Period.from_year_and_code(year, period)
    except PeriodError as exc:
        raise typer.BadParameter(f"invalid AEAT period {period!r} for year {year}") from exc


@justificante_app.command(
    "pull",
    help=tr(
        "cli.app.live.justificante.pull_help",
        default="Pull the AEAT justificante for a filed period and persist it as official evidence.",
    ),
)
def justificante_pull(
    ctx: typer.Context,
    modelo: Annotated[
        str, typer.Option("--modelo", help=tr("cli.app.live.modelo_help", default="Modelo code (e.g. 130).")),
    ],
    year: Annotated[
        int, typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help", default="Filing year.")),
    ],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.live.period_help", default="Period (e.g. 1T)."))],
) -> None:
    """Live-pull the justificante for one filed period and persist a bucket-scoped capture."""
    from ...application.live import capture_justificante_snapshot
    from ._app_live_payloads import JustificanteCaptureResult

    bucket_id = _bucket_id()
    _run_auth_preflight()
    persisted = asyncio.run(
        capture_justificante_snapshot(
            bucket_id=bucket_id,
            modelo=modelo,
            year=year,
            period=_period_option(period, year=year),
        ),
    )
    result = JustificanteCaptureResult(
        bucket_id=bucket_id,
        snapshot_id=persisted.snapshot_id,
        modelo=persisted.modelo,
        filing_year=persisted.filing_year,
        period=str(persisted.period),
        expediente_id=persisted.expediente_id,
        csv=persisted.csv,
        pdf_sha256=persisted.pdf_sha256,
        source_kind=persisted.source_kind,
        state=persisted.state.value,
        captured_at=persisted.captured_at.isoformat(),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{persisted.snapshot_id}",
        f"modelo\t{persisted.modelo}",
        f"filing_year\t{persisted.filing_year}",
        f"period\t{persisted.period}",
        f"expediente_id\t{persisted.expediente_id}",
        f"pdf_sha256\t{persisted.pdf_sha256}",
        f"source_kind\t{persisted.source_kind}",
        f"captured_at\t{persisted.captured_at.isoformat()}",
    ]
    _emit_envelope(ctx, command="app.live.justificante.pull", result=result, lines=lines)


@justificante_app.command(
    "list",
    help=tr(
        "cli.app.live.justificante.list_help",
        default="List persisted justificante captures in the active profile.",
    ),
)
def justificante_list(ctx: typer.Context) -> None:
    """List persisted justificante-capture snapshots for the active bucket."""
    from ...application.live import JustificanteCaptureSnapshotService
    from ._app_live_payloads import JustificanteListResult, JustificanteSnapshotSummaryPayload

    bucket_id = _bucket_id()
    rows = JustificanteCaptureSnapshotService(bucket_id=bucket_id).list_snapshots()
    result = JustificanteListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[
            JustificanteSnapshotSummaryPayload(
                snapshot_id=row.snapshot_id,
                modelo=row.modelo,
                filing_year=row.filing_year,
                period=str(row.period),
                pdf_sha256=row.pdf_sha256,
                state=row.state.value,
                captured_at=row.captured_at.isoformat(),
            )
            for row in rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        lines.append(f"{row.snapshot_id}\t{row.modelo}\t{row.filing_year}\t{row.period}\t{row.captured_at.isoformat()}")
    _emit_envelope(ctx, command="app.live.justificante.list", result=result, lines=lines)


@justificante_app.command(
    "view",
    help=tr(
        "cli.app.live.justificante.view_help",
        default="View one justificante capture.",
    ),
)
def justificante_view(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.justificante.snapshot_id_help",
                default="Snapshot id (or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    """Show one justificante capture's provenance for the active bucket."""
    from ...application.live import JustificanteCaptureSnapshotService
    from ._app_live_payloads import JustificanteViewResult

    bucket_id = _bucket_id()
    record = JustificanteCaptureSnapshotService(bucket_id=bucket_id).show(snapshot_id)
    result = JustificanteViewResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        modelo=record.modelo,
        filing_year=record.filing_year,
        period=str(record.period),
        expediente_id=record.expediente_id,
        csv=record.csv,
        pdf_sha256=record.pdf_sha256,
        source_kind=record.source_kind,
        state=record.state.value,
        captured_at=record.captured_at.isoformat(),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"modelo\t{record.modelo}",
        f"filing_year\t{record.filing_year}",
        f"period\t{record.period}",
        f"expediente_id\t{record.expediente_id}",
        f"pdf_sha256\t{record.pdf_sha256}",
        f"source_kind\t{record.source_kind}",
        f"state\t{record.state.value}",
        f"captured_at\t{record.captured_at.isoformat()}",
    ]
    _emit_envelope(ctx, command="app.live.justificante.view", result=result, lines=lines)
