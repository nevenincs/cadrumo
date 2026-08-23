"""Behavior handlers for read-only live expedientes snapshot commands.

The pull/list/view/latest verbs route AEAT declaration-register captures through
:func:`capture_expedientes`, :func:`capture_expedientes_bulk`, and
:class:`ExpedientesService`, then emit :class:`ExpedientesCaptureResult`,
:class:`ExpedientesListResult`, :class:`ExpedientesViewResult`, or
:class:`ExpedientesLatestResult` through :func:`_emit_envelope`.
"""

from __future__ import annotations

import asyncio
from datetime import datetime as _datetime
from typing import Protocol, TypedDict

import typer

from ...application.live import capture_expedientes_bulk
from ._app_live_auth_preflight import _emit_live_auth_preflight, _metric_line
from ._common import _emit_envelope, active_bucket_id_or_refuse, resolve_pull_year_range


def _bucket_id() -> str:
    return active_bucket_id_or_refuse()


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


def expedientes_pull(
    ctx: typer.Context,
    modelos: list[str] | None = None,
    year: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
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
    _emit_live_auth_preflight()
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


def expedientes_show(
    ctx: typer.Context,
    snapshot_id: str,
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


__all__ = ["expedientes_latest", "expedientes_list", "expedientes_pull", "expedientes_show"]
