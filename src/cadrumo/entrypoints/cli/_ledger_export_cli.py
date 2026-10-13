"""Ledger export transport, loaded only for an export invocation."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.export.tabular import ExportSerializationFormat
from ...core.i18n.render import tr
from .common import emit_envelope
from .period_parsing import _optional_canonical_period


def ledger_export(
    ctx: typer.Context,
    output: Path,
    export_kind: ExportSerializationFormat = ExportSerializationFormat.CSV,
    include_inactive: bool = False,
    period: str | None = None,
    year: int | None = None,
    actor: str | None = None,
) -> None:
    """Export canonical exact-profile ledger rows through the authenticated worker."""
    from .runtime_ledger_export_link import export_ledger_for_cli

    projection = export_ledger_for_cli(
        ctx,
        output=output,
        export_format=export_kind,
        include_inactive=include_inactive,
        period=_optional_canonical_period(period, year=year),
        actor=actor,
    )
    from ._ledger_payloads import LedgerExportPayload

    result = LedgerExportPayload.model_validate(
        {
            **projection.model_dump(mode="json", exclude={"profile_id", "output_path"}),
            "output_path": str(output),
        }
    )
    emit_envelope(
        ctx,
        command="ledger.export",
        result=result,
        lines=[
            f"{tr('cli.ledger.labels.bucket')}\t{result.bucket_id}",
            f"{tr('cli.ledger.labels.export_id')}\t{result.export_id}",
            f"{tr('cli.ledger.labels.rows')}\t{result.row_count}",
            f"{tr('cli.ledger.labels.sha256')}\t{result.sha256}",
            f"{tr('cli.ledger.labels.output')}\t{output}",
        ],
    )
