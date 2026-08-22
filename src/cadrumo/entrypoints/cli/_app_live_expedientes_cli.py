"""Typer registration for read-only live expedientes snapshot commands.

The pull/list/view/latest verbs route AEAT declaration-register captures through
:func:`capture_expedientes`, :func:`capture_expedientes_bulk`, and
:class:`ExpedientesService`, then emit :class:`ExpedientesCaptureResult`,
:class:`ExpedientesListResult`, :class:`ExpedientesViewResult`, or
:class:`ExpedientesLatestResult` through :func:`_emit_envelope`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime as _datetime
from typing import Annotated, Protocol, TypedDict

import typer

from ...application.live import capture_expedientes_bulk
from ...core.i18n import tr
from ._app_execution_policies import ENCRYPTED_READ, LIVE_PROFILE_WRITE, declare_metadata_group
from ._app_live_auth_preflight import _metric_line, resolve_active_bucket, run_auth_preflight
from ._command_policy import command_execution_policy
from ._common import _emit_envelope, resolve_pull_year_range

_active_bucket_id: Callable[[], str] | None = None
_auth_preflight: Callable[[], None] | None = None

expedientes_app = typer.Typer(
    name="expedientes",
    help=tr("cli.app.live.expedientes.app_help", default="AEAT expedientes snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
declare_metadata_group(expedientes_app)


def register_expedientes_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
    auth_preflight: Callable[[], None],
) -> None:
    """Mount live expedientes commands on the live app."""
    global _active_bucket_id, _auth_preflight
    _active_bucket_id = active_bucket_id
    _auth_preflight = auth_preflight
    app.add_typer(expedientes_app, name="expedientes")


def _bucket_id() -> str:
    return resolve_active_bucket(_active_bucket_id, family="expedientes")


class _ExpedientesRowDict(TypedDict):
    snapshot_id: str
    captured_at: str
    source_url: str
    declaration_count: int


class _SnapshotWithCapturedAt(Protocol):
    """Minimal surface required by :func:`_expedientes_row`."""

    @property
    def captured_at(self) -> _datetime: ...


def _expedientes_row(snapshot: _SnapshotWithCapturedAt) -> _ExpedientesRowDict:
    captured_at = snapshot.captured_at
    return {
        "snapshot_id": str(getattr(snapshot, "snapshot_id", "")),
        "captured_at": captured_at.isoformat(),
        "source_url": str(getattr(snapshot, "source_url", "")),
        "declaration_count": len(getattr(snapshot, "declarations", ())),
    }


@expedientes_app.command(
    "pull",
    help=tr(
        "cli.app.live.expedientes.pull_help",
        default="Pull the AEAT declaration register and persist bucket-scoped snapshot evidence.",
    ),
)
def expedientes_pull(
    ctx: typer.Context,
    modelos: Annotated[
        list[str] | None,
        typer.Option(
            "--modelo",
            help=tr(
                "cli.app.live.expedientes.pull_modelo_help",
                default="Modelo code to include. Repeat or omit with --from-year/--to-year for a bulk pull.",
            ),
        ),
    ] = None,
    year: Annotated[
        int | None,
        typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help", default="Filing year.")),
    ] = None,
    year_from: Annotated[
        int | None,
        typer.Option("--from-year", min=2000, max=2099, help=tr("cli.app.live.from_year_help")),
    ] = None,
    year_to: Annotated[
        int | None,
        typer.Option("--to-year", min=2000, max=2099, help=tr("cli.app.live.to_year_help")),
    ] = None,
) -> None:
    """Live-walk the AEAT declaration register and persist snapshots.

    A single-modelo pull delegates to :func:`capture_expedientes`; bulk
    year-range pulls delegate to :func:`capture_expedientes_bulk`. Successful
    captures become :class:`PersistedExpedientesSnapshot` records rendered as
    :class:`ExpedientesCaptureResult`, while failed rows are rendered as
    :class:`ExpedientesCaptureFailurePayload`.
    """
    from ...application.live import capture_expedientes
    from ._app_live_payloads import ExpedientesCaptureFailurePayload, ExpedientesCaptureResult

    bucket_id = _bucket_id()
    run_auth_preflight(_auth_preflight, family="expedientes")
    selected_modelos = tuple(modelos or ())
    if len(selected_modelos) == 1 and year is not None and year_from is None and year_to is None:
        persisted = asyncio.run(capture_expedientes(bucket_id=bucket_id, modelo=selected_modelos[0], year=year))
        result = ExpedientesCaptureResult(
            bucket_id=bucket_id,
            snapshot_id=persisted.snapshot_id,
            captured_at=persisted.captured_at.isoformat(),
            persisted_at=persisted.persisted_at.isoformat(),
            declaration_count=len(persisted.declarations),
            source_url=persisted.source_url,
        )
        lines = [
            f"bucket\t{bucket_id}",
            f"snapshot_id\t{persisted.snapshot_id}",
            f"captured_at\t{persisted.captured_at.isoformat()}",
            f"declaration_count\t{len(persisted.declarations)}",
            f"source_url\t{persisted.source_url}",
        ]
        _emit_envelope(ctx, command="app.live.expedientes.pull", result=result, lines=lines)
        return

    resolved_from, resolved_to = resolve_pull_year_range(year=year, year_from=year_from, year_to=year_to)
    report = asyncio.run(
        capture_expedientes_bulk(
            bucket_id=bucket_id,
            year_from=resolved_from,
            year_to=resolved_to,
            modelos=selected_modelos or None,
        ),
    )
    lines = [
        f"bucket\t{bucket_id}",
        _metric_line("modelo_count", len(report.modelos)),
        _metric_line("year_from", report.year_from),
        _metric_line("year_to", report.year_to),
        _metric_line("captured_snapshot_count", report.captured_snapshot_count),
        _metric_line("declaration_count", report.declaration_count),
        _metric_line("failed_count", len(report.failures)),
        _metric_line("snapshot_ids", ",".join(report.snapshot_ids)),
    ]
    lines.extend(
        _metric_line(
            "failure",
            "\t".join((failure.modelo, str(failure.year), failure.error_type, failure.message)),
        )
        for failure in report.failures
    )
    result = ExpedientesCaptureResult(
        mode="bulk",
        bucket_id=report.bucket_id,
        modelos=list(report.modelos),
        year_from=report.year_from,
        year_to=report.year_to,
        captured_snapshot_count=report.captured_snapshot_count,
        declaration_count=report.declaration_count,
        snapshot_ids=list(report.snapshot_ids),
        failed_count=len(report.failures),
        failures=[
            ExpedientesCaptureFailurePayload(
                modelo=failure.modelo,
                year=failure.year,
                error_type=failure.error_type,
                message=failure.message,
            )
            for failure in report.failures
        ],
    )
    _emit_envelope(ctx, command="app.live.expedientes.pull", result=result, lines=lines)


@expedientes_app.command(
    "list",
    help=tr(
        "cli.app.live.expedientes.list_help",
        default="List persisted expedientes snapshots in the active profile.",
    ),
)
def expedientes_list(ctx: typer.Context) -> None:
    """List persisted expedientes snapshots for the active bucket.

    The command reads :class:`ExpedientesService` storage and emits
    :class:`ExpedientesListResult` summary rows; per-declaration fields remain
    on :class:`ExpedientesViewResult`.
    """
    from ...application.live import ExpedientesService
    from ._app_live_payloads import ExpedientesListResult, ExpedienteSnapshotSummaryPayload

    bucket_id = _bucket_id()
    rows = ExpedientesService().list_snapshots(bucket_id=bucket_id)
    result = ExpedientesListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[ExpedienteSnapshotSummaryPayload(**_expedientes_row(row)) for row in rows],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        lines.append(f"{row.snapshot_id}\t{row.captured_at.isoformat()}\tdeclarations={len(row.declarations)}")
    _emit_envelope(ctx, command="app.live.expedientes.list", result=result, lines=lines)


@expedientes_app.command(
    "view",
    help=tr(
        "cli.app.live.expedientes.view_help",
        default="View one expedientes snapshot.",
    ),
)
def expedientes_show(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.expedientes.snapshot_id_help",
                default="Snapshot id (or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    """Show one expedientes snapshot with all its declaration rows.

    The id is resolved by :class:`ExpedientesService` as a
    :class:`PersistedExpedientesSnapshot` and projected as
    :class:`ExpedientesViewResult` with :class:`ExpedienteDeclarationPayload`
    rows, preserving the read-only live-observation boundary.
    """
    from ...application.live import ExpedientesService
    from ._app_live_payloads import ExpedienteDeclarationPayload, ExpedientesViewResult

    bucket_id = _bucket_id()
    record = ExpedientesService().show(bucket_id=bucket_id, snapshot_id=snapshot_id)
    result = ExpedientesViewResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        captured_at=record.captured_at.isoformat(),
        source_url=record.source_url,
        declaration_count=len(record.declarations),
        declarations=[
            ExpedienteDeclarationPayload(
                modelo=declaration.modelo,
                ejercicio=declaration.ejercicio,
                period=declaration.period.registry_token,
                expediente_id=declaration.expediente_id,
                estado=declaration.estado,
                tipo_solicitud=declaration.tipo_solicitud,
                observaciones=declaration.observaciones,
                presented_at=declaration.presented_at.isoformat(),
                justificante_link_text=declaration.justificante_link_text,
                archive_link_text=declaration.archive_link_text,
                declaration_copy_link_text=declaration.declaration_copy_link_text,
                justificante_cell_index=declaration.justificante_cell_index,
                archive_cell_index=declaration.archive_cell_index,
                declaration_copy_cell_index=declaration.declaration_copy_cell_index,
                mode=declaration.mode,
            )
            for declaration in record.declarations
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"declaration_count\t{len(record.declarations)}",
    ]
    for declaration in record.declarations:
        lines.append(
            f"{declaration.expediente_id}\t{declaration.modelo}\t{declaration.ejercicio}\t"
            f"{declaration.period}\t{declaration.estado}\t{declaration.presented_at.isoformat()}",
        )
    _emit_envelope(ctx, command="app.live.expedientes.view", result=result, lines=lines)


@expedientes_app.command(
    "latest",
    help=tr(
        "cli.app.live.expedientes.latest_help",
        default="Show the most recent expedientes snapshot in the active profile.",
    ),
)
def expedientes_latest(ctx: typer.Context) -> None:
    """Show the most recent expedientes snapshot, or report none.

    A bucket with no captured expedientes from :class:`ExpedientesService`
    emits :class:`ExpedientesLatestResult` with ``snapshot_id=None`` rather than
    attempting a live pull.
    """
    from ...application.live import ExpedientesService
    from ._app_live_payloads import ExpedientesLatestResult

    bucket_id = _bucket_id()
    record = ExpedientesService().latest(bucket_id=bucket_id)
    if record is None:
        empty = ExpedientesLatestResult(bucket_id=bucket_id, snapshot_id=None)
        _emit_envelope(
            ctx,
            command="app.live.expedientes.latest",
            result=empty,
            lines=[f"bucket\t{bucket_id}", "snapshot_id\t-"],
        )
        return
    result = ExpedientesLatestResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        captured_at=record.captured_at.isoformat(),
        source_url=record.source_url,
        declaration_count=len(record.declarations),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"declaration_count\t{len(record.declarations)}",
    ]
    _emit_envelope(ctx, command="app.live.expedientes.latest", result=result, lines=lines)


command_execution_policy(LIVE_PROFILE_WRITE)(expedientes_pull)
for _callback in (expedientes_list, expedientes_show, expedientes_latest):
    command_execution_policy(ENCRYPTED_READ)(_callback)
