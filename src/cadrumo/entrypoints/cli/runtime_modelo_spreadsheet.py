"""Submit the four registered spreadsheet operations for one bound profile."""

from __future__ import annotations

from pathlib import Path
from typing import Never

import typer
from pydantic import BaseModel

from ...application.modelo.modelo_spreadsheet_operation_contracts import (
    MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
    MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE,
    MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
    ModeloSpreadsheetCalculateOutcome,
    ModeloSpreadsheetCalculateProjection,
    ModeloSpreadsheetCalculateRequest,
    ModeloSpreadsheetExportOutcome,
    ModeloSpreadsheetExportProjection,
    ModeloSpreadsheetExportRequest,
    ModeloSpreadsheetProjection,
    ModeloSpreadsheetPullOutcome,
    ModeloSpreadsheetPullProjection,
    ModeloSpreadsheetPullRequest,
    ModeloSpreadsheetRequest,
    ModeloSpreadsheetVerifyOutcome,
    ModeloSpreadsheetVerifyProjection,
    ModeloSpreadsheetVerifyRequest,
    SpreadsheetOutputPathRefusal,
    SpreadsheetRowIngressRefusal,
    SpreadsheetSnapshotMismatchRefusal,
)
from ...application.operations.public_period import PublicPeriod
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.hashing import sha256_file
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .errors import CliRecordedOperationError
from .runtime_profile_binding import bound_profile_client, require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)

_OUTPUT_PATH_REFUSAL_CODE = "REFUSED_MODELO_EXPORT_OUTPUT_PATH"
_SNAPSHOT_REFUSAL_CODE = "REFUSED_OUTBOUND_STORAGE_CONFLICT"
_OUTPUT_PATH_REASONS = {
    "empty": "path is empty",
    "existing_directory": "path is an existing directory",
    "existing_file": "path is an existing file",
    "missing_parent": "parent directory does not exist",
    "parent_not_directory": "parent path is not a directory",
    "publication_failed": "file publication failed",
}
_ROW_INGRESS_REASONS = {
    "undeclared_grouping": "the row grouping is not declared",
    "caller_binding_substitution": "the row uses a binding not declared for this grouping",
    "unknown_field": "the row contains an unknown binding",
    "duplicate_cell_coordinate": "the row contains a duplicate binding coordinate",
    "row_ownership_collision": "two row sets claim the same row",
}
type ModeloSpreadsheetRegisteredOutcome = (
    ModeloSpreadsheetExportOutcome
    | ModeloSpreadsheetPullOutcome
    | ModeloSpreadsheetCalculateOutcome
    | ModeloSpreadsheetVerifyOutcome
)


def _invalid[ProjectionT: BaseModel](completed: RegisteredOperationCompletion[ProjectionT]) -> Never:
    raise submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def _submit[ProjectionT: BaseModel](
    ctx: typer.Context,
    request: ModeloSpreadsheetRequest,
    *,
    definition_id: str,
    result_type: type[ProjectionT],
) -> RegisteredOperationCompletion[ProjectionT]:
    client = require_profile_client(ctx, expected_profile_id=request.profile_id)
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=120,
        allow_refusal_detail=True,
    )


def _refuse_from_correlated_outcome(
    outcome: ModeloSpreadsheetRegisteredOutcome,
    *,
    operation_id: str,
    refusal_code: str,
    effect: OperationEffect,
) -> Never:
    """Translate only closed refusal facts that match their terminal receipt."""
    refusal = outcome.refusal
    context: dict[str, object]
    translated_message: str
    if isinstance(refusal, SpreadsheetOutputPathRefusal):
        if outcome.operation != "export" or refusal_code != _OUTPUT_PATH_REFUSAL_CODE:
            raise submitted_operation_error(
                operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=OperationTerminalCondition.REFUSED,
                effect=effect,
                refusal_code=refusal_code,
            )
        context = {
            "output_path": refusal.output_path,
            "reason": _OUTPUT_PATH_REASONS[refusal.reason],
        }
        translated_message = "application.modelo.errors.export_output_path_invalid"
    elif isinstance(refusal, SpreadsheetRowIngressRefusal):
        if outcome.operation != "pull" or refusal_code != MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE:
            raise submitted_operation_error(
                operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=OperationTerminalCondition.REFUSED,
                effect=effect,
                refusal_code=refusal_code,
            )
        context = {
            "row_index": refusal.row_index,
            "validation_error_type": "row_set_ingress",
            "validation_error_detail": _ROW_INGRESS_REASONS[refusal.reason],
        }
        translated_message = "application.calculations.row_set.errors.row_assembly_failed"
    elif isinstance(refusal, SpreadsheetSnapshotMismatchRefusal):
        if outcome.operation not in {"pull", "calculate"} or refusal_code != _SNAPSHOT_REFUSAL_CODE:
            raise submitted_operation_error(
                operation_id,
                RuntimeRefusalCode.INVALID_FRAME.value,
                terminal_condition=OperationTerminalCondition.REFUSED,
                effect=effect,
                refusal_code=refusal_code,
            )
        context = {
            "spreadsheet_id": refusal.spreadsheet_id,
            "metadata_match": refusal.metadata_match,
            "workbook_modelo": refusal.workbook_modelo,
            "snapshot_modelo": str(refusal.snapshot_modelo),
            "workbook_revision": refusal.workbook_revision,
            "snapshot_revision": str(refusal.snapshot_revision),
            "workbook_engine_version": refusal.workbook_engine_version,
            "expected_engine_version": refusal.expected_engine_version,
            "workbook_registry_sha": refusal.workbook_registry_sha,
            "snapshot_registry_sha": refusal.snapshot_registry_sha,
        }
        translated_message = "adapters.google.calc_sheets.errors.workbook_snapshot_mismatch"
    else:
        raise submitted_operation_error(
            operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.REFUSED,
            effect=effect,
            refusal_code=refusal_code,
        )
    raise CliRecordedOperationError(
        refusal_code,
        context=context,
        translated_message=translated_message,
    )


def _correlate[OutcomeT: ModeloSpreadsheetRegisteredOutcome, ProjectionT: ModeloSpreadsheetProjection](
    completed: RegisteredOperationCompletion[OutcomeT],
    *,
    request: ModeloSpreadsheetRequest,
    operation: str,
    projection_type: type[ProjectionT],
    expected_effect: OperationEffect,
) -> ProjectionT:
    outcome = completed.projection
    if (
        outcome.profile_id != request.profile_id
        or outcome.modelo != request.modelo
        or outcome.period != request.period
        or outcome.operation != operation
    ):
        _invalid(completed)
    result = outcome.result
    if outcome.outcome == "succeeded":
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.effect is not expected_effect
            or completed.refusal_code is not None
            or result is None
            or outcome.refusal is not None
            or not isinstance(result, projection_type)
            or result.profile_id != request.profile_id
            or result.modelo != request.modelo
            or result.revision != outcome.revision
            or result.period != request.period
        ):
            _invalid(completed)
        return result

    refusal = outcome.refusal
    if (
        outcome.outcome != "refused"
        or result is not None
        or refusal is None
        or completed.terminal_condition is not OperationTerminalCondition.REFUSED
        or completed.refusal_code is None
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UNKNOWN}
    ):
        _invalid(completed)
    if isinstance(refusal, SpreadsheetOutputPathRefusal):
        if (
            operation != "export"
            or not isinstance(request, ModeloSpreadsheetExportRequest)
            or refusal.output_path != request.output_path
            or completed.refusal_code != _OUTPUT_PATH_REFUSAL_CODE
            or completed.effect not in {OperationEffect.NONE, OperationEffect.UNKNOWN}
        ):
            _invalid(completed)
    elif isinstance(refusal, SpreadsheetRowIngressRefusal):
        if (
            operation != "pull"
            or completed.refusal_code != MODELO_SPREADSHEET_ROW_INGRESS_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
        ):
            _invalid(completed)
    elif isinstance(refusal, SpreadsheetSnapshotMismatchRefusal):
        if (
            operation not in {"pull", "calculate"}
            or not isinstance(request, (ModeloSpreadsheetPullRequest, ModeloSpreadsheetCalculateRequest))
            or refusal.spreadsheet_id != request.spreadsheet_id
            or completed.refusal_code != _SNAPSHOT_REFUSAL_CODE
            or completed.effect is not OperationEffect.NONE
        ):
            _invalid(completed)
    else:
        _invalid(completed)
    _refuse_from_correlated_outcome(
        outcome,
        operation_id=str(completed.operation_id),
        refusal_code=completed.refusal_code,
        effect=completed.effect,
    )


def export_modelo_spreadsheet(
    ctx: typer.Context,
    *,
    modelo: str,
    period: PublicPeriod,
    output: Path,
    replace_existing: bool,
    prefill_relations: bool,
) -> ModeloSpreadsheetExportProjection:
    """Publish an export workbook through the exact-profile worker."""
    client = bound_profile_client(ctx)
    absolute_output = output.absolute()
    request = ModeloSpreadsheetExportRequest(
        profile_id=client.profile_id,
        modelo=modelo,
        period=period,
        output_path=str(absolute_output),
        replace_existing=replace_existing,
        prefill_relations=prefill_relations,
    )
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_SPREADSHEET_EXPORT_OPERATION_DEFINITION_ID,
        result_type=ModeloSpreadsheetExportOutcome,
    )
    projection = _correlate(
        completed,
        request=request,
        operation="export",
        projection_type=ModeloSpreadsheetExportProjection,
        expected_effect=OperationEffect.UPDATED,
    )
    if projection.output_path != request.output_path or projection.prefill_relations != request.prefill_relations:
        _invalid(completed)
    return projection


def pull_modelo_spreadsheet(
    ctx: typer.Context,
    *,
    modelo: str,
    period: PublicPeriod,
    spreadsheet_id: str,
    assemble_observations: bool,
) -> ModeloSpreadsheetPullProjection:
    """Read and normalize workbook edits through the exact-profile worker."""
    client = bound_profile_client(ctx)
    request = ModeloSpreadsheetPullRequest(
        profile_id=client.profile_id,
        modelo=modelo,
        period=period,
        spreadsheet_id=spreadsheet_id,
        assemble_observations=assemble_observations,
    )
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_SPREADSHEET_PULL_OPERATION_DEFINITION_ID,
        result_type=ModeloSpreadsheetPullOutcome,
    )
    projection = _correlate(
        completed,
        request=request,
        operation="pull",
        projection_type=ModeloSpreadsheetPullProjection,
        expected_effect=OperationEffect.NONE,
    )
    if (
        projection.spreadsheet_id != request.spreadsheet_id
        or (
            not request.assemble_observations
            and (projection.assembled_groupings or projection.assembled_observation_count)
        )
        or any(edit.value is None for edit in projection.operator_edits)
        or any(edit.value is None for edit in projection.binding_edits)
        or any(edit.value is None for edit in projection.relation_edits)
        or any(cell.value is None for row in projection.row_set_edits for cell in row.cells)
    ):
        _invalid(completed)
    return projection


def calculate_modelo_spreadsheet(
    ctx: typer.Context,
    *,
    modelo: str,
    period: PublicPeriod,
    spreadsheet_id: str,
) -> ModeloSpreadsheetCalculateProjection:
    """Run the matching-workbook calculation through the exact-profile worker."""
    client = bound_profile_client(ctx)
    request = ModeloSpreadsheetCalculateRequest(
        profile_id=client.profile_id,
        modelo=modelo,
        period=period,
        spreadsheet_id=spreadsheet_id,
    )
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_SPREADSHEET_CALCULATE_OPERATION_DEFINITION_ID,
        result_type=ModeloSpreadsheetCalculateOutcome,
    )
    projection = _correlate(
        completed,
        request=request,
        operation="calculate",
        projection_type=ModeloSpreadsheetCalculateProjection,
        expected_effect=OperationEffect.NONE,
    )
    if projection.spreadsheet_id != request.spreadsheet_id:
        _invalid(completed)
    return projection


def verify_modelo_spreadsheet(
    ctx: typer.Context,
    *,
    modelo: str,
    period: PublicPeriod,
    scenario_path: Path | None,
) -> ModeloSpreadsheetVerifyProjection:
    """Run the parity harness through the exact-profile worker."""
    client = bound_profile_client(ctx)
    absolute_scenario = scenario_path.absolute() if scenario_path is not None else None
    scenario_digest = sha256_file(absolute_scenario) if absolute_scenario is not None else None
    request = ModeloSpreadsheetVerifyRequest(
        profile_id=client.profile_id,
        modelo=modelo,
        period=period,
        scenario_path=str(absolute_scenario) if absolute_scenario is not None else None,
        scenario_sha256=scenario_digest,
    )
    completed = _submit(
        ctx,
        request,
        definition_id=MODELO_SPREADSHEET_VERIFY_OPERATION_DEFINITION_ID,
        result_type=ModeloSpreadsheetVerifyOutcome,
    )
    return _correlate(
        completed,
        request=request,
        operation="verify",
        projection_type=ModeloSpreadsheetVerifyProjection,
        expected_effect=OperationEffect.UPDATED,
    )


__all__ = [
    "calculate_modelo_spreadsheet",
    "export_modelo_spreadsheet",
    "pull_modelo_spreadsheet",
    "verify_modelo_spreadsheet",
]
