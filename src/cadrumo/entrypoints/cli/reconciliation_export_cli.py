"""Export a selected saved difference review through the authenticated worker."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo.reconciliation_export_operation import (
    RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID,
    ReconciliationExportXlsxProjection,
    ReconciliationExportXlsxRequest,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ...core.json_contract import OutputSchema
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import emit_envelope
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


class ReconciliationWorkbookResult(OutputSchema):
    """Published-byte and selection receipt for a saved reconciliation review."""

    publication: ReconciliationExportXlsxProjection


def export_reconciliation_cli(
    ctx: typer.Context,
    output: Path,
    event_id: str | None = None,
    work_unit_id: str | None = None,
    all_history: bool = False,
    replace_existing: bool = False,
) -> None:
    """Export exactly one selected record, work unit, or explicit full history."""
    if sum((event_id is not None, work_unit_id is not None, all_history)) != 1:
        raise typer.BadParameter(tr("cli.app.modelo.reconcile.export_selector_required"))
    client = bound_profile_client(ctx)
    request = ReconciliationExportXlsxRequest(
        profile_id=client.profile_id,
        event_id=event_id,
        work_unit_id=work_unit_id,
        all_history=all_history,
        output_path=str(output.resolve()),
        replace_existing=replace_existing,
        report_language=OutputLanguage(active_output_language()),
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=RECONCILIATION_EXPORT_XLSX_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ReconciliationExportXlsxProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    result = completed.projection
    if (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.effect is not OperationEffect.UPDATED
        or completed.refusal_code is not None
        or result.profile_id != request.profile_id
        or result.event_id != request.event_id
        or result.work_unit_id != request.work_unit_id
        or result.all_history != request.all_history
        or result.output_path != request.output_path
    ):
        raise invalid_completion_error(completed)
    emit_envelope(
        ctx,
        command="modelo.reconcile.export",
        result=ReconciliationWorkbookResult(publication=result),
        lines=(
            f"output_path\t{result.output_path}",
            f"reconciliations\t{result.reconciliation_count}",
            f"differences\t{result.difference_count}",
            f"advisories\t{result.advisory_count}",
        ),
    )
