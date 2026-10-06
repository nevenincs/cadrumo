"""Outbound workbook commands for ``aeat app modelo spreadsheet``.

Local XLSX export presents an exact-profile operation projection. Google
review publication uses its separately registered outbound operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...application.operations.public_period import PublicPeriod
from ...core.period import Period, PeriodError
from ._modelo_spreadsheet_payloads import (
    ModeloSpreadsheetExportResult,
    ModeloSpreadsheetPushResult,
)
from .common import emit_envelope
from .errors import CliRefusedBoundaryError
from .runtime_modelo_spreadsheet import (
    export_modelo_spreadsheet,
)
from .runtime_modelo_spreadsheet_push import run_google_sheets_export
from .runtime_profile_binding import bound_profile_client

if TYPE_CHECKING:
    import typer


def filing_period_or_refusal(*, modelo: str, period: str, year: int) -> Period:
    """Validate the explicit filing coordinate before submitting an export."""
    try:
        return Period.from_year_and_code(year, period)
    except PeriodError as exc:
        raise CliRefusedBoundaryError(
            translated_message="cli.app.modelo.spreadsheet.push.snapshot_failure",
            context={"modelo": modelo, "period": period, "year": year},
        ) from exc


def modelo_spreadsheet_push(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    prefill_relations: bool = False,
    dry_run: bool = False,
) -> None:
    """Export the registry calculation surface for a modelo + period to a Google Sheets workbook."""
    active, result = run_google_sheets_export(
        bound_profile_client(ctx),
        modelo=modelo,
        period=period,
        year=year,
        prefill_relations=prefill_relations,
        dry_run=dry_run,
    )

    export_result = ModeloSpreadsheetPushResult(
        profile=active,
        modelo=result.modelo,
        revision=result.revision,
        period=result.period,
        year=result.filing_year,
        engine_version=result.engine_version,
        registry_sha=result.registry_sha,
        root_folder_id=result.root_folder_id or "",
        dry_run=result.dry_run,
        spreadsheet_exists=result.spreadsheet_exists,
        folder_id=result.folder_id,
        spreadsheet_id=result.spreadsheet_id,
        spreadsheet_url=result.spreadsheet_url,
        value_cells_written=result.value_cells_written,
        formula_cells_written=result.formula_cells_written,
        protected_ranges_written=result.protected_ranges_written,
        tab_count=result.tab_count,
        ranges_to_clear=list(result.ranges_to_clear),
        value_cells_changed=result.value_cells_changed,
        value_cells_unchanged=result.value_cells_unchanged,
        formula_cells_to_write=result.formula_cells_to_write,
    )
    lines = (
        "operation\tmodelo.spreadsheet.push",
        f"profile\t{active}",
        f"modelo\t{result.modelo}",
        f"revision\t{result.revision}",
        f"period\t{result.period}",
        f"year\t{result.filing_year}",
        f"dry_run\t{result.dry_run}",
        f"folder_id\t{result.folder_id}",
        f"spreadsheet_id\t{result.spreadsheet_id}",
        f"spreadsheet_url\t{result.spreadsheet_url}",
        f"value_cells_written\t{result.value_cells_written}",
        f"formula_cells_written\t{result.formula_cells_written}",
        f"protected_ranges_written\t{result.protected_ranges_written}",
        f"tab_count\t{result.tab_count}",
    )
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.push",
        result=export_result,
        lines=lines,
    )


def modelo_spreadsheet_export(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    output: Path,
    replace_existing: bool = False,
    prefill_relations: bool = False,
) -> None:
    """Export the registry calculation surface for a modelo + period to a local ``.xlsx`` workbook."""
    request_period = PublicPeriod.from_period(filing_period_or_refusal(modelo=modelo, period=period, year=year))
    projection = export_modelo_spreadsheet(
        ctx,
        modelo=modelo,
        period=request_period,
        output=output,
        replace_existing=replace_existing,
        prefill_relations=prefill_relations,
    )

    export_result = ModeloSpreadsheetExportResult(
        modelo=str(projection.modelo),
        revision=str(projection.revision),
        period=projection.period.code,
        year=projection.period.filing_year,
        output_path=str(output),
        byte_size=projection.byte_size,
        sha256=projection.sha256,
        tab_names=list(projection.tab_names),
        casilla_count=projection.casilla_count,
        prefill_relations=projection.prefill_relations,
    )
    lines = (
        "operation\tmodelo.spreadsheet.export",
        f"modelo\t{export_result.modelo}",
        f"revision\t{export_result.revision}",
        f"period\t{export_result.period}",
        f"year\t{export_result.year}",
        f"output_path\t{export_result.output_path}",
        f"byte_size\t{export_result.byte_size}",
        f"sha256\t{export_result.sha256}",
        f"casilla_count\t{export_result.casilla_count}",
    )
    emit_envelope(ctx, command="modelo.spreadsheet.export", result=export_result, lines=lines)
