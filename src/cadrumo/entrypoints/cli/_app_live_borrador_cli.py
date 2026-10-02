"""Behavior handlers for live Modelo 100 borrador snapshot commands.

The commands submit exact-profile worker requests and present the canonical
human projections. They do not file, submit, or refresh live AEAT data.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal, TypedDict

import typer

from ...application.live.borrador_100_operation import Borrador100SnapshotSummary
from ...application.live.snapshot_base import SnapshotLifecycleState, SnapshotLifecycleStateValue, SnapshotStateFilter
from ...application.operations.public_period import PublicPeriod
from ...core.i18n.render import tr
from ...core.period import Period
from ._app_live_borrador_payloads import (
    Borrador100ImportResult,
    Borrador100LatestResult,
    Borrador100ListResult,
    Borrador100SnapshotSummaryPayload,
    Borrador100ViewResult,
)
from .common import emit_envelope
from .runtime_live_borrador import import_borrador_100_for_cli, read_borrador_100_for_cli


class _BorradorRow(TypedDict):
    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: SnapshotLifecycleStateValue


def borrador_100_import(ctx: typer.Context, file: Path, filing_year: int, period: str = "0A") -> None:
    """Import one local PDF through the exact-profile registered worker."""
    try:
        resolved_period = Period.from_year_and_code(filing_year, period)
    except ValueError as exc:
        raise typer.BadParameter(tr("cli.app.live.borrador.import_period_invalid")) from exc

    projection = import_borrador_100_for_cli(
        ctx,
        source_path=file,
        filing_year=filing_year,
        period=PublicPeriod.from_period(resolved_period),
    )
    snapshot = projection.snapshot
    bucket_id = str(projection.profile_id)
    result = Borrador100ImportResult(
        bucket_id=bucket_id,
        **_borrador_row(snapshot),
        extraction_profile_id=projection.extraction_profile_id,
        extraction_coverage=format(Decimal(projection.extraction_coverage.decimal), "f"),
        artefact_kind=projection.artefact_kind,
        source_pdf_sha256=str(projection.source_pdf_sha256),
        blank_casillas=sorted(projection.blank_casillas),
        warnings=list(projection.warnings),
    )
    lines = [
        f"bucket\t{bucket_id}",
        f"snapshot_id\t{snapshot.snapshot_id}",
        f"filing_year\t{snapshot.filing_year}",
        f"period\t{snapshot.period.to_period()}",
        f"extraction_profile_id\t{projection.extraction_profile_id}",
        f"extraction_coverage\t{format(Decimal(projection.extraction_coverage.decimal), 'f')}",
        f"artefact_kind\t{projection.artefact_kind}",
        f"binding_count\t{snapshot.binding_count}",
        f"blank_casillas\t{len(projection.blank_casillas)}",
    ]
    emit_envelope(ctx, command="app.live.borrador.100.import", result=result, lines=lines)


def borrador_100_list(ctx: typer.Context, state: SnapshotStateFilter = SnapshotStateFilter.ACTIVE) -> None:
    """List persisted Modelo 100 borrador snapshots for the bound profile."""
    projection = read_borrador_100_for_cli(ctx, kind="list", state=state)
    bucket_id = str(projection.profile_id)
    rows = projection.rows
    result = Borrador100ListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[Borrador100SnapshotSummaryPayload(**_borrador_row(row)) for row in rows],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    lines.extend(
        f"{row.snapshot_id}\t{row.filing_year}\t{row.period.to_period()}\t{row.captured_at.isoformat()}\t"
        f"bindings={row.binding_count}\t{row.state.value}"
        for row in rows
    )
    emit_envelope(ctx, command="app.live.borrador.100.list", result=result, lines=lines)


def borrador_100_show(ctx: typer.Context, snapshot_id: str) -> None:
    """Show one Modelo 100 borrador snapshot with its binding values."""
    projection = read_borrador_100_for_cli(ctx, kind="view", snapshot_id=snapshot_id)
    record = projection.snapshot
    if record is None:
        raise ValueError("borrador view projection is missing its snapshot")
    bucket_id = str(projection.profile_id)
    binding_values = {
        key: format(value, "f") if isinstance(value, Decimal) else str(value)
        for key, value in record.binding_map().items()
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
        f"period\t{record.period.to_period()}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"binding_count\t{record.binding_count}",
        f"state\t{record.state.value}",
    ]
    emit_envelope(ctx, command="app.live.borrador.100.view", result=result, lines=lines)


def borrador_100_latest(ctx: typer.Context, filing_year: int) -> None:
    """Show the most recent active Modelo 100 borrador snapshot for a year."""
    projection = read_borrador_100_for_cli(ctx, kind="latest", filing_year=filing_year)
    bucket_id = str(projection.profile_id)
    record = projection.snapshot
    if record is None:
        result = Borrador100LatestResult(bucket_id=bucket_id, filing_year=filing_year, snapshot_id=None)
        emit_envelope(
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
        period=str(record.period.to_period()),
        source_url=record.source_url,
        binding_count=record.binding_count,
        state=_active_borrador_state(record.state),
    )
    emit_envelope(
        ctx,
        command="app.live.borrador.100.latest",
        result=result,
        lines=[
            f"bucket\t{bucket_id}",
            f"snapshot_id\t{record.snapshot_id}",
            f"filing_year\t{record.filing_year}",
            f"period\t{record.period.to_period()}",
            f"captured_at\t{record.captured_at.isoformat()}",
            f"binding_count\t{record.binding_count}",
        ],
    )


def _borrador_row(snapshot: Borrador100SnapshotSummary) -> _BorradorRow:
    """Project canonical snapshot metadata into the existing CLI summary."""
    return _BorradorRow(
        snapshot_id=str(snapshot.snapshot_id),
        filing_year=snapshot.filing_year,
        period=str(snapshot.period.to_period()),
        captured_at=snapshot.captured_at.isoformat(),
        source_url=str(snapshot.source_url),
        binding_count=snapshot.binding_count,
        state=snapshot.state,
    )


def _active_borrador_state(state: SnapshotLifecycleState) -> Literal["active"]:
    """Require the registered latest result to contain an active record."""
    if state is not SnapshotLifecycleState.ACTIVE:
        raise ValueError("latest Borrador snapshot must be active")
    return "active"


__all__ = ["borrador_100_import", "borrador_100_latest", "borrador_100_list", "borrador_100_show"]
