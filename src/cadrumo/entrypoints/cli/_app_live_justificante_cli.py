"""Behavior handlers for exact-profile live justificante operations.

Pull uses the registered capture worker; list and view use registered local
snapshot reads. The emitted payloads are :class:`JustificanteCaptureResult`,
:class:`JustificanteListResult`, and :class:`JustificanteViewResult`.
"""

from __future__ import annotations

import typer

from ...core.modelo import Modelo
from ...core.period import Period, PeriodError
from .common import emit_envelope
from .runtime_justificante_capture import capture_justificante_for_cli
from .runtime_profile_binding import bound_profile_client


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
    """Pull one signed AEAT receipt through the exact-profile worker."""
    from ._app_live_justificante_payloads import JustificanteCaptureResult

    profile_id = bound_profile_client(ctx).profile_id
    bucket_id = str(profile_id)
    persisted = capture_justificante_for_cli(
        ctx,
        profile_id=profile_id,
        modelo=modelo,
        year=year,
        period=_period_option(period, year=year),
    ).projection
    result = JustificanteCaptureResult(
        bucket_id=bucket_id,
        snapshot_id=persisted.snapshot_id,
        modelo=Modelo(persisted.modelo),
        filing_year=persisted.filing_year,
        period=persisted.period,
        expediente_id=persisted.expediente_id,
        csv=persisted.csv,
        pdf_sha256=persisted.pdf_sha256,
        source_kind=persisted.source_kind,
        state=persisted.state,
        captured_at=persisted.captured_at,
        justificante_metadata_registered=persisted.justificante_metadata_registered,
        calendar_evidence_available=persisted.calendar_evidence_available,
        modelo_filing_record_required=persisted.modelo_filing_record_required,
        filing_evidence_stamped=persisted.filing_evidence_stamped,
        filing_record_id=persisted.filing_record_id,
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
        f"justificante_metadata_registered\t{str(persisted.justificante_metadata_registered).lower()}",
        f"calendar_evidence_available\t{str(persisted.calendar_evidence_available).lower()}",
        f"modelo_filing_record_required\t{str(persisted.modelo_filing_record_required).lower()}",
        f"filing_evidence_stamped\t{str(persisted.filing_evidence_stamped).lower()}",
    ]
    if persisted.filing_record_id is not None:
        lines.append(f"filing_record_id\t{persisted.filing_record_id}")
    else:
        lines.append(
            "modelo_filing_record_import\t"
            f"aeat app modelo filing-record import WORK_UNIT_ID --evidence-kind aeat_live_capture "
            f"--evidence-id {persisted.csv} --set CASILLA=VALUE",
        )
    emit_envelope(ctx, command="app.live.justificante.pull", result=result, lines=lines)


def justificante_list(ctx: typer.Context) -> None:
    """List the active receipt summaries returned by the registered profile read.

    Rows are projected into the existing :class:`JustificanteListResult` envelope.
    """
    from ...application.live.snapshot_base import SnapshotLifecycleState
    from ._app_live_justificante_payloads import JustificanteListResult, JustificanteSnapshotSummaryPayload
    from .runtime_justificante_read import read_justificante_list_for_cli

    projection = read_justificante_list_for_cli(ctx).projection
    bucket_id = projection.bucket_id
    result = JustificanteListResult(
        bucket_id=bucket_id,
        count=projection.count,
        rows=[
            JustificanteSnapshotSummaryPayload(
                snapshot_id=row.snapshot_id,
                modelo=Modelo(row.modelo),
                filing_year=row.filing_year,
                period=row.period,
                pdf_sha256=row.pdf_sha256,
                state=SnapshotLifecycleState(row.state),
                captured_at=row.captured_at,
            )
            for row in projection.rows
        ],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{projection.count}"]
    for row in projection.rows:
        lines.append(f"{row.snapshot_id}\t{row.modelo}\t{row.filing_year}\t{row.period}\t{row.captured_at.isoformat()}")
    emit_envelope(ctx, command="app.live.justificante.list", result=result, lines=lines)


def justificante_view(
    ctx: typer.Context,
    snapshot_id: str,
) -> None:
    """Show one receipt provenance record through the registered profile read.

    The bounded result is emitted as :class:`JustificanteViewResult`.
    """
    from ...application.calculations.observations_repository import ObservationSourceKind
    from ...application.live.snapshot_base import SnapshotLifecycleState
    from ._app_live_justificante_payloads import JustificanteViewResult
    from .runtime_justificante_read import read_justificante_show_for_cli

    record = read_justificante_show_for_cli(ctx, snapshot_id=snapshot_id).projection
    bucket_id = record.bucket_id
    result = JustificanteViewResult(
        bucket_id=bucket_id,
        snapshot_id=record.snapshot_id,
        modelo=Modelo(record.modelo),
        filing_year=record.filing_year,
        period=record.period,
        expediente_id=record.expediente_id,
        csv=record.csv,
        pdf_sha256=record.pdf_sha256,
        source_kind=ObservationSourceKind(record.source_kind),
        state=SnapshotLifecycleState(record.state),
        captured_at=record.captured_at,
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
        f"state\t{record.state}",
        f"captured_at\t{record.captured_at.isoformat()}",
    ]
    emit_envelope(ctx, command="app.live.justificante.view", result=result, lines=lines)


__all__ = ["justificante_list", "justificante_pull", "justificante_view"]
