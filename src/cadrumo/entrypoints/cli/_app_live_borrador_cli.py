"""Behavior handlers for live Modelo 100 borrador snapshot commands.

The list/view/latest commands expose bucket-local
:class:`Borrador100Snapshot` records captured from AEAT through
:class:`Borrador100SnapshotService`. They emit :class:`Borrador100ListResult`,
:class:`Borrador100ViewResult`, and :class:`Borrador100LatestResult`; they do
not file, submit, or refresh live AEAT data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, TypedDict

import typer

from ...application.live.borrador_100 import Borrador100Snapshot, Borrador100SnapshotService
from ...application.live.snapshot_base import (
    SnapshotLifecycleState,
    SnapshotLifecycleStateValue,
    SnapshotStateFilter,
)
from ._app_live_borrador_payloads import (
    Borrador100ImportResult,
    Borrador100LatestResult,
    Borrador100ListResult,
    Borrador100SnapshotSummaryPayload,
    Borrador100ViewResult,
)
from ._common import active_bucket_id_or_refuse, emit_envelope


class _BorradorRow(TypedDict):
    snapshot_id: str
    filing_year: int
    period: str
    captured_at: str
    source_url: str
    binding_count: int
    state: SnapshotLifecycleStateValue


def borrador_100_import(ctx: typer.Context, file: Path, filing_year: int, period: str = "0A") -> None:
    """Import a local Modelo 100 borrador PDF into the encrypted snapshot store.

    Parses ``file`` through :func:`~adapters.inbound.borrador.parser.parse_borrador`
    in :attr:`BorradorParseMode.REGISTRY_PROFILE` mode, driven by the
    ``borrador_pdf`` extraction profile the registry declares for
    ``filing_year``/``period``, then persists the observed casilla values through
    the existing :meth:`Borrador100SnapshotService.capture`. The snapshot the
    ``list`` / ``view`` / ``latest`` verbs already read is the same record.

    The profile's ``min_coverage`` is authority: a PDF that yields fewer target
    casillas than the profile requires raises
    :exc:`BorradorParseError` and nothing is persisted. A target casilla found
    blank on the page is reported in ``blank_casillas`` and contributes no
    binding value; it is never persisted as a zero.

    Only the parser's digest-derived source reference is stored. The operator's
    filesystem path never reaches the snapshot.
    """
    from ...adapters.inbound.borrador.parser import parse_borrador
    from ...adapters.inbound.borrador.schema import BorradorParseMode
    from ...core.i18n import tr
    from ...core.period import Period
    from ...domain.calculations.registry.authority import bundled_authority
    from ...domain.calculations.registry.schema_extraction import ExtractionSurface

    bucket_id = active_bucket_id_or_refuse()
    try:
        resolved_period = Period.from_year_and_code(filing_year, period)
    except ValueError as exc:
        raise typer.BadParameter(tr("cli.app.live.borrador.import_period_invalid")) from exc

    registry = bundled_authority().snapshot("100", filing_year=filing_year, period=period)
    profiles = tuple(
        profile
        for profile in registry.revision.extraction_profiles
        if profile.surface == ExtractionSurface.BORRADOR_PDF
    )
    if len(profiles) != 1:
        raise typer.BadParameter(tr("cli.app.live.borrador.import_profile_unresolved"))
    profile = profiles[0]

    observation = parse_borrador(
        file,
        extraction_profile=profile,
        parse_mode=BorradorParseMode.REGISTRY_PROFILE,
    )

    if observation.ejercicio != str(filing_year):
        raise typer.BadParameter(tr("cli.app.live.borrador.import_ejercicio_mismatch"))

    binding_values: dict[str, Decimal | str] = {}
    blank_casillas: list[str] = []
    for casilla in observation.values:
        if casilla.printed_value is None:
            blank_casillas.append(casilla.casilla_id)
            continue
        value = casilla.printed_value
        binding_values[f"casilla.{casilla.casilla_id}"] = value if isinstance(value, Decimal) else str(value)

    coverage = observation.extraction_coverage
    if coverage is None:
        raise typer.BadParameter(tr("cli.app.live.borrador.import_coverage_absent"))

    record = Borrador100SnapshotService(bucket_id=bucket_id).capture(
        filing_year=filing_year,
        period=resolved_period,
        captured_at=datetime.now(UTC),
        source_url=f"file-import:sha256:{observation.source_pdf_sha256}",
        binding_values=binding_values,
    )
    result = Borrador100ImportResult(
        bucket_id=bucket_id,
        **_borrador_row(record),
        extraction_profile_id=profile.id,
        extraction_coverage=format(coverage, "f"),
        artefact_kind=observation.artefact_kind.value,
        source_pdf_sha256=observation.source_pdf_sha256,
        blank_casillas=sorted(blank_casillas),
        warnings=list(observation.warnings),
    )
    lines = [
        f"bucket	{bucket_id}",
        f"snapshot_id	{record.snapshot_id}",
        f"filing_year	{record.filing_year}",
        f"period	{record.period}",
        f"extraction_profile_id	{profile.id}",
        f"extraction_coverage	{format(coverage, 'f')}",
        f"artefact_kind	{observation.artefact_kind.value}",
        f"binding_count	{len(record.binding_values)}",
        f"blank_casillas	{len(blank_casillas)}",
    ]
    emit_envelope(ctx, command="app.live.borrador.100.import", result=result, lines=lines)


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
    emit_envelope(ctx, command="app.live.borrador.100.list", result=result, lines=lines)


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
    emit_envelope(ctx, command="app.live.borrador.100.view", result=result, lines=lines)


def borrador_100_latest(ctx: typer.Context, filing_year: int) -> None:
    """Show the most recent active Modelo 100 borrador snapshot for a year."""
    bucket_id = active_bucket_id_or_refuse()
    record = Borrador100SnapshotService(bucket_id=bucket_id).latest_for_year(filing_year=filing_year)
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
        period=str(record.period),
        source_url=record.source_url,
        binding_count=len(record.binding_values),
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
            f"period\t{record.period}",
            f"captured_at\t{record.captured_at.isoformat()}",
            f"binding_count\t{len(record.binding_values)}",
        ],
    )


def _borrador_row(snapshot: Borrador100Snapshot) -> _BorradorRow:
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


def _borrador_state(state: SnapshotLifecycleState) -> SnapshotLifecycleStateValue:
    """Narrow the lifecycle enum to the three members a summary row may carry."""
    match state:
        case SnapshotLifecycleState.ACTIVE:
            return SnapshotLifecycleState.ACTIVE
        case SnapshotLifecycleState.SUPERSEDED:
            return SnapshotLifecycleState.SUPERSEDED
        case SnapshotLifecycleState.DISCARDED:
            return SnapshotLifecycleState.DISCARDED


def _active_borrador_state(state: SnapshotLifecycleState) -> Literal["active"]:
    """Require the service's latest-snapshot contract to return an active record."""
    if state is not SnapshotLifecycleState.ACTIVE:
        raise ValueError("latest Borrador snapshot must be active")
    return "active"


__all__ = ["borrador_100_import", "borrador_100_latest", "borrador_100_list", "borrador_100_show"]
