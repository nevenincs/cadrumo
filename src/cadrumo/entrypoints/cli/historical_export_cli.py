"""Select the retained immutable calculation of an exact historical filing."""

from __future__ import annotations

from pathlib import Path

import typer

from ...core.i18n.render import tr
from .calculation_review_cli import export_calculation_review_cli
from .runtime_modelo_filing_record_view import read_modelo_filing_record_view


def export_historical_filing_cli(
    ctx: typer.Context, filing_record_id: str, output: Path, replace_existing: bool = False
) -> None:
    """Export the selected filing's retained calculation, refusing missing historical content."""
    record, _, historical = read_modelo_filing_record_view(ctx, filing_record_id=filing_record_id)
    if historical.availability != "available":
        raise typer.BadParameter(tr("cli.app.modelo.filing_record.export_missing"))
    export_calculation_review_cli(
        ctx,
        record.calculation_revision_id,
        output,
        replace_existing,
        filing_record_id=filing_record_id,
        command="modelo.filing_record.export",
    )
