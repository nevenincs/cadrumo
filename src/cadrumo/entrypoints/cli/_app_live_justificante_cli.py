"""Typer registration for live :class:`JustificanteCaptureSnapshot` commands.

The pull command delegates to :func:`capture_justificante_snapshot_outcome`;
the list and view commands read :class:`JustificanteCaptureSnapshotService`
storage. The emitted payloads are :class:`JustificanteCaptureResult`,
:class:`JustificanteListResult`, and :class:`JustificanteViewResult`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Annotated

import typer

from ...core import Modelo, Period, PeriodError
from ...core.i18n import tr
from ._app_execution_policies import ENCRYPTED_READ, LIVE_PROFILE_WRITE, declare_metadata_group
from ._app_live_auth_preflight import resolve_active_bucket, run_auth_preflight
from ._command_policy import command_execution_policy
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
declare_metadata_group(justificante_app)


def register_justificante_commands(
    app: typer.Typer,
    *,
    active_bucket_id: Callable[[], str],
    auth_preflight: Callable[[], None],
) -> None:
    """Mount the bucket-scoped justificante snapshot commands on the live app."""
    global _active_bucket_id, _auth_preflight
    _active_bucket_id = active_bucket_id
    _auth_preflight = auth_preflight
    app.add_typer(justificante_app, name="justificante")


def _bucket_id() -> str:
    return resolve_active_bucket(_active_bucket_id, family="justificante")


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
        str,
        typer.Option("--modelo", help=tr("cli.app.live.modelo_help", default="Modelo code (e.g. 130).")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", min=2000, max=2099, help=tr("cli.app.live.year_help", default="Filing year.")),
    ],
    period: Annotated[str, typer.Option("--period", help=tr("cli.app.live.period_help", default="Period (e.g. 1T)."))],
) -> None:
    """Pull one signed AEAT receipt into a persisted :class:`JustificanteCaptureSnapshot`.

    The command delegates to :func:`capture_justificante_snapshot_outcome`, so
    the remote read, content-addressed snapshot write, parsed justificante
    metadata registration, and optional local filing-evidence stamp share the
    same application boundary before emitting :class:`JustificanteCaptureResult`.
    """
    from ...application.live import capture_justificante_snapshot_outcome
    from ._app_live_payloads import JustificanteCaptureResult

    bucket_id = _bucket_id()
    run_auth_preflight(_auth_preflight, family="justificante")
    outcome = asyncio.run(
        capture_justificante_snapshot_outcome(
            bucket_id=bucket_id,
            modelo=modelo,
            year=year,
            period=_period_option(period, year=year),
        ),
    )
    persisted = outcome.snapshot
    result = JustificanteCaptureResult(
        bucket_id=bucket_id,
        snapshot_id=persisted.snapshot_id,
        modelo=Modelo(persisted.modelo),
        filing_year=persisted.filing_year,
        period=persisted.period.registry_token,
        expediente_id=persisted.expediente_id,
        csv=persisted.csv,
        pdf_sha256=persisted.pdf_sha256,
        source_kind=persisted.source_kind,
        state=persisted.state,
        captured_at=persisted.captured_at,
        justificante_metadata_registered=outcome.justificante_metadata_registered,
        calendar_evidence_available=outcome.justificante_metadata_registered,
        modelo_filing_record_required=not outcome.filing_evidence_stamped,
        filing_evidence_stamped=outcome.filing_evidence_stamped,
        filing_record_id=outcome.filing_record_id,
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{persisted.snapshot_id}",
        f"modelo\t{persisted.modelo}",
        f"filing_year\t{persisted.filing_year}",
        f"period\t{persisted.period.registry_token}",
        f"expediente_id\t{persisted.expediente_id}",
        f"pdf_sha256\t{persisted.pdf_sha256}",
        f"source_kind\t{persisted.source_kind}",
        f"captured_at\t{persisted.captured_at.isoformat()}",
        f"justificante_metadata_registered\t{str(outcome.justificante_metadata_registered).lower()}",
        f"calendar_evidence_available\t{str(outcome.justificante_metadata_registered).lower()}",
        f"modelo_filing_record_required\t{str(not outcome.filing_evidence_stamped).lower()}",
        f"filing_evidence_stamped\t{str(outcome.filing_evidence_stamped).lower()}",
    ]
    if outcome.filing_record_id is not None:
        lines.append(f"filing_record_id\t{outcome.filing_record_id}")
    else:
        lines.append(
            "modelo_filing_record_import\t"
            f"aeat app modelo filing-record import WORK_UNIT_ID --evidence-kind aeat_live_capture "
            f"--evidence-id {persisted.csv} --set CASILLA=VALUE",
        )
    _emit_envelope(ctx, command="app.live.justificante.pull", result=result, lines=lines)


@justificante_app.command(
    "list",
    help=tr(
        "cli.app.live.justificante.list_help",
        default="List persisted justificante captures in the active profile.",
    ),
)
def justificante_list(ctx: typer.Context) -> None:
    """List active captures from :class:`JustificanteCaptureSnapshotService`.

    Rows are :class:`JustificanteSnapshotSummaryPayload` projections emitted in
    a :class:`JustificanteListResult` envelope.
    """
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
                modelo=Modelo(row.modelo),
                filing_year=row.filing_year,
                period=row.period.registry_token,
                pdf_sha256=row.pdf_sha256,
                state=row.state,
                captured_at=row.captured_at,
            )
            for row in rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    for row in rows:
        lines.append(
            f"{row.snapshot_id}\t{row.modelo}\t{row.filing_year}\t{row.period.registry_token}"
            f"\t{row.captured_at.isoformat()}"
        )
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
    """Show one :class:`JustificanteCaptureSnapshot` provenance record.

    The snapshot is resolved through :class:`JustificanteCaptureSnapshotService`
    and projected as :class:`JustificanteViewResult`.
    """
    from ...application.live import JustificanteCaptureSnapshotService
    from ._app_live_payloads import JustificanteViewResult

    bucket_id = _bucket_id()
    record = JustificanteCaptureSnapshotService(bucket_id=bucket_id).show(snapshot_id)
    result = JustificanteViewResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        modelo=Modelo(record.modelo),
        filing_year=record.filing_year,
        period=record.period.registry_token,
        expediente_id=record.expediente_id,
        csv=record.csv,
        pdf_sha256=record.pdf_sha256,
        source_kind=record.source_kind,
        state=record.state,
        captured_at=record.captured_at,
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{record.snapshot_id}",
        f"modelo\t{record.modelo}",
        f"filing_year\t{record.filing_year}",
        f"period\t{record.period.registry_token}",
        f"expediente_id\t{record.expediente_id}",
        f"pdf_sha256\t{record.pdf_sha256}",
        f"source_kind\t{record.source_kind}",
        f"state\t{record.state.value}",
        f"captured_at\t{record.captured_at.isoformat()}",
    ]
    _emit_envelope(ctx, command="app.live.justificante.view", result=result, lines=lines)


command_execution_policy(LIVE_PROFILE_WRITE)(justificante_pull)
for _callback in (justificante_list, justificante_view):
    command_execution_policy(ENCRYPTED_READ)(_callback)
