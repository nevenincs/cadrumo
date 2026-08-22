"""Typer registration for read-only live deudas snapshot commands.

The list/view/latest verbs read persisted AEAT debts snapshots through
:class:`DeudasService` and emit :class:`DeudasListResult`,
:class:`DeudasViewResult` or :class:`DeudasLatestResult` through
:func:`_emit_envelope`.

There is deliberately NO ``pull`` verb here. Fetching the debts consulta needs
an operator-authorised specimen of that AEAT page, and the adapter's
read-landing guard refuses every landing until one exists, so this surface
reads only what a future capture would persist. These three verbs cross no
wire, persist nothing, and take no auth preflight: an empty register is
reported as empty rather than reaching for AEAT.

Nothing displayed here is a calculation input. An AEAT-imposed liability is
downstream of the taxpayer's tax position for a period rather than part of it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import typer

from ...core.i18n import tr
from ._app_execution_policies import ENCRYPTED_READ, declare_metadata_group
from ._app_live_auth_preflight import resolve_active_bucket
from ._command_policy import command_execution_policy
from ._common import _emit_envelope

_active_bucket_id: Callable[[], str] | None = None

deudas_app = typer.Typer(
    name="deudas",
    help=tr("cli.app.live.deudas.app_help", default="AEAT deudas snapshots (read-only)."),
    no_args_is_help=True,
    add_completion=False,
)
declare_metadata_group(deudas_app)


def register_deudas_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
) -> None:
    """Mount live deudas commands on the live app.

    Takes no ``auth_preflight``: every verb in this family reads persisted
    bucket storage and none contacts AEAT, so there is no live session to
    preflight.
    """
    global _active_bucket_id
    _active_bucket_id = active_bucket_id
    app.add_typer(deudas_app, name="deudas")


def _bucket_id() -> str:
    return resolve_active_bucket(_active_bucket_id, family="deudas")


@deudas_app.command(
    "list",
    help=tr(
        "cli.app.live.deudas.list_help",
        default="List persisted deudas snapshots in the active profile.",
    ),
)
def deudas_list(ctx: typer.Context) -> None:
    """List persisted deudas snapshots for the active bucket.

    Reads :class:`DeudasService` storage and emits
    :class:`DeudasListResult` summary rows; per-liability fields remain on
    :class:`DeudasViewResult`.
    """
    from ...application.live import DeudasService
    from ._app_live_payloads import DeudasListResult, DeudaSnapshotSummaryPayload

    bucket_id = _bucket_id()
    rows = DeudasService().list_snapshots(bucket_id=bucket_id)
    result = DeudasListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[
            DeudaSnapshotSummaryPayload(
                snapshot_id=str(row.snapshot_id),
                captured_at=row.captured_at.isoformat(),
                source_url=row.source_url,
                deuda_count=len(row.deudas),
            )
            for row in rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    lines.extend(f"{row.snapshot_id}\t{row.captured_at.isoformat()}\tdeudas={len(row.deudas)}" for row in rows)
    _emit_envelope(ctx, command="app.live.deudas.list", result=result, lines=lines)


@deudas_app.command(
    "view",
    help=tr(
        "cli.app.live.deudas.view_help",
        default="View one deudas snapshot.",
    ),
)
def deudas_view(
    ctx: typer.Context,
    snapshot_id: Annotated[
        str,
        typer.Argument(
            help=tr(
                "cli.app.live.deudas.snapshot_id_help",
                default="Snapshot id (or unambiguous prefix).",
            ),
        ),
    ],
) -> None:
    """Show one deudas snapshot with every AEAT-reported liability it holds.

    The id is resolved by :class:`DeudasService` as a
    :class:`PersistedDeudasSnapshot` and projected as
    :class:`DeudasViewResult` with :class:`DeudaRowPayload` rows, preserving
    the read-only live-observation boundary. Amounts are emitted as strings so
    the persisted ``Decimal`` scale survives the JSON boundary, and direction
    is reported on its own field rather than as a sign.
    """
    from ...application.live import DeudasService
    from ._app_live_payloads import DeudaRowPayload, DeudasViewResult

    bucket_id = _bucket_id()
    record = DeudasService().show(bucket_id=bucket_id, snapshot_id=snapshot_id)
    result = DeudasViewResult(
        bucket_id=bucket_id,
        snapshot_id=str(record.snapshot_id),
        captured_at=record.captured_at.isoformat(),
        source_url=record.source_url,
        deuda_count=len(record.deudas),
        deudas=[
            DeudaRowPayload(
                clave_liquidacion=deuda.clave_liquidacion,
                objeto_tributario=deuda.objeto_tributario.value,
                importe_pendiente=str(deuda.importe_pendiente),
                direccion=deuda.direccion.value,
                periodo=deuda.periodo.registry_token if deuda.periodo is not None else None,
                situacion=deuda.situacion,
                mode=deuda.mode,
            )
            for deuda in record.deudas
        ],
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"deuda_count\t{len(record.deudas)}",
    ]
    lines.extend(
        f"{deuda.clave_liquidacion}\t{deuda.objeto_tributario.value}\t{deuda.importe_pendiente}\t"
        f"{deuda.direccion.value}\t{deuda.periodo.registry_token if deuda.periodo is not None else '-'}\t"
        f"{deuda.situacion}"
        for deuda in record.deudas
    )
    _emit_envelope(ctx, command="app.live.deudas.view", result=result, lines=lines)


@deudas_app.command(
    "latest",
    help=tr(
        "cli.app.live.deudas.latest_help",
        default="Show the most recent deudas snapshot in the active profile.",
    ),
)
def deudas_latest(ctx: typer.Context) -> None:
    """Show the most recent deudas snapshot, or report none.

    A bucket with no captured deudas from :class:`DeudasService` emits
    :class:`DeudasLatestResult` with ``snapshot_id=None`` rather than
    attempting a live pull.
    """
    from ...application.live import DeudasService
    from ._app_live_payloads import DeudasLatestResult

    bucket_id = _bucket_id()
    record = DeudasService().latest(bucket_id=bucket_id)
    if record is None:
        empty = DeudasLatestResult(bucket_id=bucket_id, snapshot_id=None)
        _emit_envelope(
            ctx,
            command="app.live.deudas.latest",
            result=empty,
            lines=[f"bucket\t{bucket_id}", "snapshot_id\t-"],
        )
        return
    result = DeudasLatestResult(
        bucket_id=bucket_id,
        snapshot_id=str(record.snapshot_id),
        captured_at=record.captured_at.isoformat(),
        source_url=record.source_url,
        deuda_count=len(record.deudas),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"deuda_count\t{len(record.deudas)}",
    ]
    _emit_envelope(ctx, command="app.live.deudas.latest", result=result, lines=lines)


for _callback in (deudas_list, deudas_view, deudas_latest):
    command_execution_policy(ENCRYPTED_READ)(_callback)
