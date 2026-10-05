"""Workbook transport and calculation commands for ``aeat app modelo spreadsheet``.

The export, pull, calculate, and verify leaves present exact-profile registered
operation projections. The older Google ``push`` route retains its own runtime
bridge.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...application.modelo.modelo_spreadsheet_operation_projections import (
    ModeloSpreadsheetCalculateProjection,
    ModeloSpreadsheetPullProjection,
    ModeloSpreadsheetVerifyProjection,
)
from ...application.operations.public_period import PublicPeriod
from ...core.period import Period, PeriodError
from ._modelo_spreadsheet_payloads import (
    ModeloSpreadsheetCalculateCasillaPayload,
    ModeloSpreadsheetCalculateResult,
    ModeloSpreadsheetExportResult,
    ModeloSpreadsheetPullRelationEditPayload,
    ModeloSpreadsheetPullResult,
    ModeloSpreadsheetPushResult,
    ModeloSpreadsheetVerifyDivergencePayload,
    ModeloSpreadsheetVerifyResult,
)
from .common import emit_envelope
from .errors import CliRefusedBoundaryError
from .runtime_modelo_spreadsheet import (
    calculate_modelo_spreadsheet,
    export_modelo_spreadsheet,
    pull_modelo_spreadsheet,
    verify_modelo_spreadsheet,
)
from .runtime_modelo_spreadsheet_push import run_google_sheets_export
from .runtime_profile_binding import bound_profile_client

if TYPE_CHECKING:
    import typer


def filing_period_or_refusal(*, modelo: str, period: str, year: int) -> Period:
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


def _verify_result(projection: ModeloSpreadsheetVerifyProjection) -> ModeloSpreadsheetVerifyResult:
    """Project the correlated worker result onto the public verify schema."""
    return ModeloSpreadsheetVerifyResult(
        profile=str(projection.profile_id),
        modelo=str(projection.modelo),
        revision=str(projection.revision),
        period=projection.period.code,
        year=projection.period.filing_year,
        spreadsheet_id=projection.spreadsheet_id,
        spreadsheet_url=projection.spreadsheet_url,
        verdict=projection.verdict,
        aeat_oracle_present=projection.aeat_oracle_present,
        computed_count=projection.computed_count,
        divergence_count=projection.divergence_count,
        divergences=[
            ModeloSpreadsheetVerifyDivergencePayload.model_validate(divergence.model_dump(mode="json"))
            for divergence in projection.divergences
        ],
    )


def _verify_lines(projection: ModeloSpreadsheetVerifyProjection) -> list[str]:
    """Render the stable tabular projection of a parity report."""
    lines = [
        "operation\tmodelo.spreadsheet.verify",
        f"profile\t{projection.profile_id}",
        f"modelo\t{projection.modelo}",
        f"revision\t{projection.revision}",
        f"period\t{projection.period.code}",
        f"year\t{projection.period.filing_year}",
        f"spreadsheet_url\t{projection.spreadsheet_url}",
        f"verdict\t{projection.verdict}",
        f"aeat_oracle_present\t{projection.aeat_oracle_present}",
        f"computed_count\t{projection.computed_count}",
        f"divergence_count\t{projection.divergence_count}",
    ]
    for divergence in projection.divergences:
        lines.append(
            f"divergence\t{divergence.casilla_id}\tlocal={divergence.local}"
            f"\tsheets={divergence.sheets}\taeat={divergence.aeat}",
        )
    return lines


def modelo_spreadsheet_verify(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    scenario_path: Path | None = None,
) -> None:
    """Run a three-way parity check across AEAT oracle, local Decimal runtime, and Sheets."""
    request_period = PublicPeriod.from_period(filing_period_or_refusal(modelo=modelo, period=period, year=year))
    projection = verify_modelo_spreadsheet(
        ctx,
        modelo=modelo,
        period=request_period,
        scenario_path=scenario_path,
    )
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.verify",
        result=_verify_result(projection),
        lines=tuple(_verify_lines(projection)),
    )


def _pull_result(projection: ModeloSpreadsheetPullProjection) -> ModeloSpreadsheetPullResult:
    """Project the worker's complete pull facts into the established CLI schema."""
    payload: dict[str, object] = {
        "operation": "modelo.spreadsheet.pull",
        "profile": str(projection.profile_id),
        "modelo": str(projection.modelo),
        "revision": str(projection.revision),
        "period": projection.period.code,
        "year": projection.period.filing_year,
        "spreadsheet_id": projection.spreadsheet_id,
        "metadata_match": projection.metadata_match,
        "metadata": projection.metadata.model_dump(mode="json"),
        "cells_read": projection.cells_read,
        "operator_edits_total": projection.operator_edits_total,
        "operator_edits_populated": projection.operator_edits_populated,
        "binding_edits_populated": projection.binding_edits_populated,
        "relation_edits_populated": projection.relation_edits_populated,
        "operator_edits": [edit.model_dump(mode="json") for edit in projection.operator_edits],
        "binding_edits": [edit.model_dump(mode="json") for edit in projection.binding_edits],
        "relation_edits": [
            ModeloSpreadsheetPullRelationEditPayload.model_validate(edit.model_dump(mode="json"))
            for edit in projection.relation_edits
        ],
        "row_set_edits_populated": projection.row_set_edits_populated,
        "row_set_cells_populated": projection.row_set_cells_populated,
        "assembled_groupings": [
            {
                "grouping": group.grouping,
                "source_kind": group.source_kind,
                "observation_count": group.observation_count,
                "observations": [observation.model_dump(mode="json") for observation in group.observations],
            }
            for group in projection.assembled_groupings
        ],
        "assembled_observation_count": projection.assembled_observation_count,
        "row_set_edits": [row_set.model_dump(mode="json") for row_set in projection.row_set_edits],
    }
    return ModeloSpreadsheetPullResult.model_validate(payload)


def _pull_lines(projection: ModeloSpreadsheetPullProjection) -> list[str]:
    """Render the established stable tabular projection of a workbook pull."""
    lines: list[str] = [
        "operation\tmodelo.spreadsheet.pull",
        f"profile\t{projection.profile_id}",
        f"modelo\t{projection.modelo}",
        f"revision\t{projection.revision}",
        f"period\t{projection.period.code}",
        f"year\t{projection.period.filing_year}",
        f"spreadsheet_id\t{projection.spreadsheet_id}",
        f"metadata_match\t{projection.metadata_match}",
        f"metadata.modelo_id\t{projection.metadata.modelo_id}",
        f"metadata.revision_id\t{projection.metadata.revision_id}",
        f"metadata.registry_sha\t{projection.metadata.registry_sha}",
        f"cells_read\t{projection.cells_read}",
        f"operator_edits_populated\t{projection.operator_edits_populated}",
        f"binding_edits_populated\t{projection.binding_edits_populated}",
        f"relation_edits_populated\t{projection.relation_edits_populated}",
        f"row_set_edits_populated\t{projection.row_set_edits_populated}",
        f"row_set_cells_populated\t{projection.row_set_cells_populated}",
    ]
    for edit in projection.operator_edits:
        lines.append(f"casilla_id\t{edit.casilla_id}\t{edit.value}\t{edit.label}")
    for edit in projection.binding_edits:
        lines.append(f"binding\t{edit.binding}\t{edit.value}")
    for edit in projection.relation_edits:
        lines.append(f"relation\t{edit.relation}\t{edit.value}")
    for row_set in projection.row_set_edits:
        for cell in row_set.cells:
            lines.append(f"row_set\t{row_set.grouping}\t{cell.row_index}\t{cell.binding}\t{cell.value}")
    for assembled in projection.assembled_groupings:
        lines.append(
            f"assembled\t{assembled.grouping}\t{assembled.source_kind}\t{assembled.observation_count}",
        )
    return lines


def modelo_spreadsheet_pull(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    spreadsheet_id: str,
    assemble_observations: bool = False,
) -> None:
    """Read operator-edited cells back from a workbook into typed records."""
    request_period = PublicPeriod.from_period(filing_period_or_refusal(modelo=modelo, period=period, year=year))
    projection = pull_modelo_spreadsheet(
        ctx,
        modelo=modelo,
        period=request_period,
        spreadsheet_id=spreadsheet_id,
        assemble_observations=assemble_observations,
    )
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.pull",
        result=_pull_result(projection),
        lines=tuple(_pull_lines(projection)),
    )


def _calculate_result(projection: ModeloSpreadsheetCalculateProjection) -> ModeloSpreadsheetCalculateResult:
    """Build the typed compute result from the canonical worker projection."""
    return ModeloSpreadsheetCalculateResult(
        profile=str(projection.profile_id),
        modelo=str(projection.modelo),
        revision=str(projection.revision),
        period=projection.period.code,
        year=projection.period.filing_year,
        spreadsheet_id=projection.spreadsheet_id,
        metadata_match=projection.metadata_match,
        cells_read=projection.cells_read,
        operator_edits_populated=projection.operator_edits_populated,
        binding_edits_populated=projection.binding_edits_populated,
        relation_edits_populated=projection.relation_edits_populated,
        computed=[
            ModeloSpreadsheetCalculateCasillaPayload.model_validate(entry.model_dump(mode="json"))
            for entry in projection.computed
        ],
    )


def _calculate_lines(projection: ModeloSpreadsheetCalculateProjection) -> list[str]:
    """Render the stable tabular projection of a workbook calculation."""
    lines: list[str] = [
        "operation\tmodelo.spreadsheet.calculate",
        f"profile\t{projection.profile_id}",
        f"modelo\t{projection.modelo}",
        f"revision\t{projection.revision}",
        f"period\t{projection.period.code}",
        f"year\t{projection.period.filing_year}",
        f"spreadsheet_id\t{projection.spreadsheet_id}",
        f"metadata_match\t{projection.metadata_match}",
        f"cells_read\t{projection.cells_read}",
        f"operator_edits_populated\t{projection.operator_edits_populated}",
        f"binding_edits_populated\t{projection.binding_edits_populated}",
        f"relation_edits_populated\t{projection.relation_edits_populated}",
    ]
    for entry in projection.computed:
        lines.append(f"computed\t{entry.casilla_id}\t{entry.value}\t{entry.formula_id}")
    return lines


def modelo_spreadsheet_calculate(
    ctx: typer.Context,
    modelo: str,
    period: str,
    year: int,
    spreadsheet_id: str,
) -> None:
    """Compute casilla values from a workbook's operator edits; persist nothing."""
    request_period = PublicPeriod.from_period(filing_period_or_refusal(modelo=modelo, period=period, year=year))
    projection = calculate_modelo_spreadsheet(
        ctx,
        modelo=modelo,
        period=request_period,
        spreadsheet_id=spreadsheet_id,
    )
    emit_envelope(
        ctx,
        command="modelo.spreadsheet.calculate",
        result=_calculate_result(projection),
        lines=tuple(_calculate_lines(projection)),
    )


__all__ = [
    "modelo_spreadsheet_calculate",
    "modelo_spreadsheet_export",
    "modelo_spreadsheet_pull",
    "modelo_spreadsheet_push",
    "modelo_spreadsheet_verify",
]
