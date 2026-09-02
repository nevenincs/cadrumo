"""Behavior handlers for live :class:`JustificanteCaptureSnapshot` commands.

The pull command delegates to :func:`capture_justificante_snapshot_outcome`;
the list and view commands read :class:`JustificanteCaptureSnapshotService`
storage. The emitted payloads are :class:`JustificanteCaptureResult`,
:class:`JustificanteListResult`, and :class:`JustificanteViewResult`.
"""

from __future__ import annotations

import asyncio

import typer

from ...core.modelo import Modelo
from ...core.period import Period, PeriodError
from ._app_live_auth_preflight import emit_live_auth_preflight
from ._common import active_bucket_id_or_refuse, emit_envelope


def _period_option(period: str, *, year: int) -> Period:
    try:
        return Period.from_year_and_code(year, period)
    except PeriodError as exc:
        raise typer.BadParameter(f"invalid AEAT period {period!r} for year {year}") from exc


def justificante_pull(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
) -> None:
    """Pull one signed AEAT receipt into a persisted :class:`JustificanteCaptureSnapshot`.

    The command delegates to :func:`capture_justificante_snapshot_outcome`, so
    the remote read, content-addressed snapshot write, parsed justificante
    metadata registration, and optional local filing-evidence stamp share the
    same application boundary before emitting :class:`JustificanteCaptureResult`.
    """
    from ...application.live.justificante import capture_justificante_snapshot_outcome
    from ._app_live_justificante_payloads import JustificanteCaptureResult

    bucket_id = active_bucket_id_or_refuse()
    emit_live_auth_preflight()
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
    emit_envelope(ctx, command="app.live.justificante.pull", result=result, lines=lines)


def justificante_list(ctx: typer.Context) -> None:
    """List active captures from :class:`JustificanteCaptureSnapshotService`.

    Rows are :class:`JustificanteSnapshotSummaryPayload` projections emitted in
    a :class:`JustificanteListResult` envelope.
    """
    from ...application.live.justificante import JustificanteCaptureSnapshotService
    from ._app_live_justificante_payloads import JustificanteListResult, JustificanteSnapshotSummaryPayload

    bucket_id = active_bucket_id_or_refuse()
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
    emit_envelope(ctx, command="app.live.justificante.list", result=result, lines=lines)


def justificante_view(
    ctx: typer.Context,
    snapshot_id: str,
) -> None:
    """Show one :class:`JustificanteCaptureSnapshot` provenance record.

    The snapshot is resolved through :class:`JustificanteCaptureSnapshotService`
    and projected as :class:`JustificanteViewResult`.
    """
    from ...application.live.justificante import JustificanteCaptureSnapshotService
    from ._app_live_justificante_payloads import JustificanteViewResult

    bucket_id = active_bucket_id_or_refuse()
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
    emit_envelope(ctx, command="app.live.justificante.view", result=result, lines=lines)


__all__ = ["justificante_list", "justificante_pull", "justificante_view"]
