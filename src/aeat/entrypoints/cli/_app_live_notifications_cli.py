"""Typer registration for live notification commands."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated

import typer

from ...application.live import NotificationsService, capture_notifications
from ...core.i18n import tr
from ._app_live_payloads import (
    NotificationRowPayload,
    NotificationsCaptureResult,
    NotificationsLatestResult,
    NotificationsListResult,
    NotificationSnapshotListingPayload,
    NotificationsViewResult,
)
from ._common import _emit_envelope

_active_bucket_id: Callable[[], str] | None = None
_auth_preflight: Callable[[], None] | None = None


def register_notifications_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
    auth_preflight: Callable[[], None],
) -> None:
    """Mount live notification commands on the live app."""
    global _active_bucket_id, _auth_preflight
    _active_bucket_id = active_bucket_id
    _auth_preflight = auth_preflight
    app.add_typer(notifications_app, name="notifications")


def _bucket_id() -> str:
    if _active_bucket_id is None:
        raise RuntimeError("live notifications commands were not registered")
    return _active_bucket_id()


def _run_auth_preflight() -> None:
    if _auth_preflight is None:
        raise RuntimeError("live notifications commands were not registered")
    _auth_preflight()


notifications_app = typer.Typer(
    name="notifications",
    help=tr("cli.app.live.notifications.app_help", default="DEHu notification snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)


@notifications_app.command(
    "pull",
    help=tr(
        "cli.app.live.notifications.pull_help",
        default="Pull DEHu notifications and persist a bucket-scoped snapshot.",
    ),
)
def notifications_pull(ctx: typer.Context) -> None:
    """Drive the live DEHu fetch and persist flow."""
    bucket_id = _bucket_id()
    _run_auth_preflight()
    persisted = asyncio.run(capture_notifications(bucket_id=bucket_id))
    result = NotificationsCaptureResult(
        bucket_id=bucket_id,
        snapshot_id=persisted.snapshot_id,
        captured_at=persisted.captured_at.isoformat(),
        persisted_at=persisted.persisted_at.isoformat(),
        row_count=len(persisted.rows),
        source_url=persisted.source_url,
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{persisted.snapshot_id}",
        f"captured_at\t{persisted.captured_at.isoformat()}",
        f"row_count\t{len(persisted.rows)}",
        f"source_url\t{persisted.source_url}",
    ]
    _emit_envelope(ctx, command="app.live.notifications.pull", result=result, lines=lines)


@notifications_app.command(
    "list",
    help=tr(
        "cli.app.live.notifications.list_help",
        default="List persisted DEHu notification snapshots in the active profile.",
    ),
)
def notifications_list(ctx: typer.Context) -> None:
    """List persisted DEHu notification snapshots without contacting AEAT."""
    bucket_id = _bucket_id()
    rows = NotificationsService().list_snapshots(bucket_id=bucket_id)
    result = NotificationsListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[
            NotificationSnapshotListingPayload(
                snapshot_id=r.snapshot_id,
                captured_at=r.captured_at.isoformat(),
                row_count=len(r.rows),
            )
            for r in rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for r in rows:
        lines.append(f"{r.snapshot_id}\t{r.captured_at.isoformat()}\trows={len(r.rows)}")
    _emit_envelope(ctx, command="app.live.notifications.list", result=result, lines=lines)


@notifications_app.command(
    "view",
    help=tr("cli.app.live.notifications.view_help", default="View one DEHu notification snapshot."),
)
def notifications_show(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr("cli.app.live.notifications.snapshot_id_help", default="Snapshot id (or unambiguous prefix)."),
        ),
    ],
) -> None:
    """Show one persisted DEHu notification snapshot by id prefix."""
    bucket_id = _bucket_id()
    record = NotificationsService().show(bucket_id=bucket_id, snapshot_id=snapshot_id)
    result = NotificationsViewResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        captured_at=record.captured_at.isoformat(),
        source_url=record.source_url,
        row_count=len(record.rows),
        rows=[
            NotificationRowPayload(
                certificado_id=r.certificado_id,
                tipo=r.tipo,
                concepto=r.concepto,
                titular_nif=r.titular_nif,
                titular_nombre=r.titular_nombre,
                destinatario_nif=r.destinatario_nif,
                destinatario_nombre=r.destinatario_nombre,
                fecha_emision=r.fecha_emision.isoformat(),
                fecha_notificacion=r.fecha_notificacion.isoformat() if r.fecha_notificacion else None,
                modo_notificacion=r.modo_notificacion,
                leida=r.leida,
                source_url=str(r.source_url),
                mode=r.mode,
            )
            for r in record.rows
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"row_count\t{len(record.rows)}",
    ]
    for r in record.rows:
        lines.append("\t".join(f"{k}={v}" for k, v in r.model_dump(mode="json").items()))
    _emit_envelope(ctx, command="app.live.notifications.view", result=result, lines=lines)


@notifications_app.command(
    "latest",
    help=tr(
        "cli.app.live.notifications.latest_help",
        default="Show the most recent DEHu notification snapshot in the active profile.",
    ),
)
def notifications_latest(ctx: typer.Context) -> None:
    """Show the most recent DEHu notification snapshot, or report none."""
    bucket_id = _bucket_id()
    record = NotificationsService().latest(bucket_id=bucket_id)
    if record is None:
        empty = NotificationsLatestResult(bucket_id=bucket_id, snapshot_id=None)
        _emit_envelope(
            ctx,
            command="app.live.notifications.latest",
            result=empty,
            lines=[f"bucket\t{bucket_id}", "snapshot_id\t-"],
        )
        return
    result = NotificationsLatestResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        captured_at=record.captured_at.isoformat(),
        source_url=record.source_url,
        row_count=len(record.rows),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"row_count\t{len(record.rows)}",
    ]
    _emit_envelope(ctx, command="app.live.notifications.latest", result=result, lines=lines)
