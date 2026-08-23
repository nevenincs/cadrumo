"""Behavior handlers for live Modelo 100 borrador snapshot commands.

The list/view/latest commands expose bucket-local
:class:`Borrador100Snapshot` records captured from AEAT through
:class:`Borrador100SnapshotService`. They emit :class:`Borrador100ListResult`,
:class:`Borrador100ViewResult`, and :class:`Borrador100LatestResult`; they do
not file, submit, or refresh live AEAT data.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal, TypedDict

import typer

from ...application.live import (
    Borrador100SnapshotService,
    SnapshotLifecycleState,
    SnapshotStateFilter,
)
from ._app_live_payloads import (
    Borrador100LatestResult,
    Borrador100ListResult,
    Borrador100SnapshotSummaryPayload,
    Borrador100ViewResult,
)
from ._common import _emit_envelope, active_bucket_id_or_refuse


class _BorradorRow(TypedDict):
    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: Literal["active", "superseded", "discarded"]


def borrador_100_list(ctx: typer.Context, state: SnapshotStateFilter = SnapshotStateFilter.ACTIVE) -> None:
    """List persisted Modelo 100 borrador snapshots for the active bucket."""
    bucket_id = active_bucket_id_or_refuse()
    rows = Borrador100SnapshotService(bucket_id=bucket_id).list_snapshots(state=state.as_lifecycle_state())
    result = Borrador100ListResult(
        bucket_id=bucket_id,
        count=len(rows),
        rows=[Borrador100SnapshotSummaryPayload(**_borrador_row(row)) for row in rows],
    )
    lines = [f"bucket\t{bucket_id}", f"count\t{len(rows)}"]
    lines.extend(
        f"{row.snapshot_id}\t{row.filing_year}\t{row.period}\t{row.captured_at.isoformat()}\t"
        f"bindings={len(row.binding_values)}\t{row.state.value}"
        for row in rows
    )
    _emit_envelope(ctx, command="app.live.borrador.100.list", result=result, lines=lines)


def borrador_100_show(ctx: typer.Context, snapshot_id: str) -> None:
    """Show one Modelo 100 borrador snapshot with its binding values."""
    bucket_id = active_bucket_id_or_refuse()
    record = Borrador100SnapshotService(bucket_id=bucket_id).show(snapshot_id)
    binding_values = {
        key: format(value, "f") if isinstance(value, Decimal) else str(value)
        for key, value in record.binding_values.items()
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
        f"period\t{record.period}",
        f"captured_at\t{record.captured_at.isoformat()}",
        f"source_url\t{record.source_url}",
        f"binding_count\t{len(record.binding_values)}",
        f"state\t{record.state.value}",
    ]
    _emit_envelope(ctx, command="app.live.borrador.100.view", result=result, lines=lines)


def borrador_100_latest(ctx: typer.Context, filing_year: int) -> None:
    """Show the most recent active Modelo 100 borrador snapshot for a year."""
    bucket_id = active_bucket_id_or_refuse()
    record = Borrador100SnapshotService(bucket_id=bucket_id).latest_for_year(filing_year=filing_year)
    if record is None:
        result = Borrador100LatestResult(bucket_id=bucket_id, filing_year=filing_year, snapshot_id=None)
        _emit_envelope(
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
        period=str(record.period),
        source_url=record.source_url,
        binding_count=len(record.binding_values),
        state=_active_borrador_state(record.state),
    )
    _emit_envelope(
        ctx,
        command="app.live.borrador.100.latest",
        result=result,
        lines=[
            f"bucket\t{bucket_id}",
            f"snapshot_id\t{record.snapshot_id}",
            f"filing_year\t{record.filing_year}",
            f"period\t{record.period}",
            f"captured_at\t{record.captured_at.isoformat()}",
            f"binding_count\t{len(record.binding_values)}",
        ],
    )


def _borrador_row(snapshot) -> _BorradorRow:
    """Project snapshot metadata into the shared Borrador 100 summary shape."""
    return _BorradorRow(
        snapshot_id=snapshot.snapshot_id,
        filing_year=snapshot.filing_year,
        period=str(snapshot.period),
        captured_at=snapshot.captured_at.isoformat(),
        source_url=snapshot.source_url,
        binding_count=len(snapshot.binding_values),
        state=_borrador_state(snapshot.state),
    )


def _borrador_state(state: SnapshotLifecycleState) -> Literal["active", "superseded", "discarded"]:
    """Project the lifecycle enum onto the exact summary-payload vocabulary."""
    match state:
        case SnapshotLifecycleState.ACTIVE:
            return "active"
        case SnapshotLifecycleState.SUPERSEDED:
            return "superseded"
        case SnapshotLifecycleState.DISCARDED:
            return "discarded"


def _active_borrador_state(state: SnapshotLifecycleState) -> Literal["active"]:
    """Require the service's latest-snapshot contract to return an active record."""
    if state is not SnapshotLifecycleState.ACTIVE:
        raise ValueError("latest Borrador snapshot must be active")
    return "active"


__all__ = ["borrador_100_latest", "borrador_100_list", "borrador_100_show"]
