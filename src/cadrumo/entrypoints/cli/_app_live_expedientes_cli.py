"""Behavior handlers for live expedientes snapshot commands.

Capture and local snapshot reads submit exact-profile registered operations.
Every command emits its established payload through :func:`emit_envelope`.
"""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

import typer

from ...application.live.capture_mode import LiveCaptureMode
from ._app_live_auth_preflight import emit_live_auth_preflight, metric_line
from .common import active_bucket_id_or_refuse, emit_envelope, resolve_pull_year_range
from .runtime_expedientes_capture import (
    read_expedientes_bulk_capture_for_cli,
    read_expedientes_single_capture_for_cli,
)
from .runtime_expedientes_read import (
    read_expedientes_latest_for_cli,
    read_expedientes_list_for_cli,
    read_expedientes_show_for_cli,
)


def expedientes_pull(
    ctx: typer.Context,
    modelos: list[str] | None = None,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> None:
    """Capture declaration-register snapshots through the profile worker."""
    from ._app_live_expedientes_payloads import ExpedientesCaptureFailurePayload, ExpedientesCaptureResult

    bucket_id = active_bucket_id_or_refuse()
    emit_live_auth_preflight(ctx)
    profile_id = UUID(bucket_id)
    selected_modelos = tuple(modelos or ())
    if len(selected_modelos) == 1 and year is not None and year_from is None and year_to is None:
        read = read_expedientes_single_capture_for_cli(
            ctx,
            profile_id=profile_id,
            modelo=selected_modelos[0],
            year=year,
        )
        projection = read.projection
        result = ExpedientesCaptureResult(
            bucket_id=bucket_id,
            snapshot_id=projection.snapshot_id,
            captured_at=projection.captured_at.isoformat(),
            persisted_at=projection.persisted_at.isoformat(),
            declaration_count=projection.declaration_count,
            source_url=projection.source_url,
        )
        lines = [
            f"bucket\t{bucket_id}",
            f"snapshot_id\t{projection.snapshot_id}",
            f"captured_at\t{projection.captured_at.isoformat()}",
            f"declaration_count\t{projection.declaration_count}",
            f"source_url\t{projection.source_url}",
        ]
        emit_envelope(ctx, command="app.live.expedientes.pull", result=result, lines=lines)
        return

    resolved_from, resolved_to = resolve_pull_year_range(year=year, year_from=year_from, year_to=year_to)
    read = read_expedientes_bulk_capture_for_cli(
        ctx,
        profile_id=profile_id,
        year_from=resolved_from,
        year_to=resolved_to,
        modelos=selected_modelos or None,
    )
    report = read.projection
    lines = [
        f"bucket\t{bucket_id}",
        metric_line("modelo_count", len(report.modelos)),
        metric_line("year_from", report.year_from),
        metric_line("year_to", report.year_to),
        metric_line("captured_snapshot_count", report.captured_snapshot_count),
        metric_line("declaration_count", report.declaration_count),
        metric_line("failed_count", len(report.failures)),
        metric_line("snapshot_ids", ",".join(report.snapshot_ids)),
    ]
    lines.extend(
        metric_line(
            "failure",
            "\t".join((failure.modelo, str(failure.year), failure.error_type, failure.message)),
        )
        for failure in report.failures
    )
    result = ExpedientesCaptureResult(
        mode=LiveCaptureMode.BULK,
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
    emit_envelope(ctx, command="app.live.expedientes.pull", result=result, lines=lines)


def expedientes_list(ctx: typer.Context) -> None:
    """List persisted expedientes snapshots for the active bucket.

    The registered exact-profile read emits :class:`ExpedientesListResult`
    summary rows; per-declaration fields remain on :class:`ExpedientesViewResult`.
    """
    from ._app_live_expedientes_payloads import ExpedientesListResult, ExpedienteSnapshotSummaryPayload

    projection = read_expedientes_list_for_cli(ctx).projection
    bucket_id = projection.bucket_id
    result = ExpedientesListResult(
        bucket_id=bucket_id,
        count=projection.count,
        rows=[
            ExpedienteSnapshotSummaryPayload(
                snapshot_id=row.snapshot_id,
                captured_at=row.captured_at.isoformat(),
                source_url=row.source_url,
                declaration_count=row.declaration_count,
            )
            for row in projection.rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{projection.count}"]
    for row in projection.rows:
        lines.append(f"{row.snapshot_id}\t{row.captured_at.isoformat()}\tdeclarations={row.declaration_count}")
    emit_envelope(ctx, command="app.live.expedientes.list", result=result, lines=lines)


def expedientes_show(
    ctx: typer.Context,
    snapshot_id: str,
) -> None:
    """Show one expedientes snapshot with all its declaration rows.

    The id is resolved by the registered exact-profile operation and projected
    as :class:`ExpedientesViewResult` with every declaration row.
    """
    from ._app_live_expedientes_payloads import ExpedienteDeclarationPayload, ExpedientesViewResult

    projection = read_expedientes_show_for_cli(ctx, snapshot_id=snapshot_id).projection
    bucket_id = projection.bucket_id
    result = ExpedientesViewResult(
        bucket_id=bucket_id,
        snapshot_id=projection.snapshot_id,
        captured_at=projection.captured_at.isoformat(),
        source_url=projection.source_url,
        declaration_count=projection.declaration_count,
        declarations=[
            ExpedienteDeclarationPayload(
                modelo=declaration.modelo,
                ejercicio=declaration.ejercicio,
                period=declaration.period,
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
            for declaration in projection.declarations
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{projection.snapshot_id}",
        f"captured_at\t{projection.captured_at.isoformat()}",
        f"source_url\t{projection.source_url}",
        f"declaration_count\t{projection.declaration_count}",
    ]
    for declaration in projection.declarations:
        lines.append(
            f"{declaration.expediente_id}\t{declaration.modelo}\t{declaration.ejercicio}\t"
            f"{declaration.ejercicio} {declaration.period}\t{declaration.estado}\t"
            f"{declaration.presented_at.isoformat()}",
        )
    emit_envelope(ctx, command="app.live.expedientes.view", result=result, lines=lines)


def expedientes_latest(ctx: typer.Context) -> None:
    """Show the most recent expedientes snapshot, or report none.

    A bucket with no captured expedientes emits :class:`ExpedientesLatestResult`
    with ``snapshot_id=None`` rather than attempting a live pull.
    """
    from ._app_live_expedientes_payloads import ExpedientesLatestResult

    projection = read_expedientes_latest_for_cli(ctx).projection
    bucket_id = projection.bucket_id
    if projection.snapshot_id is None:
        empty = ExpedientesLatestResult(bucket_id=bucket_id, snapshot_id=None)
        emit_envelope(
            ctx,
            command="app.live.expedientes.latest",
            result=empty,
            lines=[f"bucket\t{bucket_id}", "snapshot_id\t-"],
        )
        return
    captured_at = cast(datetime, projection.captured_at)
    source_url = cast(str, projection.source_url)
    declaration_count = cast(int, projection.declaration_count)
    result = ExpedientesLatestResult(
        bucket_id=bucket_id,
        snapshot_id=projection.snapshot_id,
        captured_at=captured_at.isoformat(),
        source_url=source_url,
        declaration_count=declaration_count,
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{projection.snapshot_id}",
        f"captured_at\t{captured_at.isoformat()}",
        f"declaration_count\t{declaration_count}",
    ]
    emit_envelope(ctx, command="app.live.expedientes.latest", result=result, lines=lines)


__all__ = ["expedientes_latest", "expedientes_list", "expedientes_pull", "expedientes_show"]
