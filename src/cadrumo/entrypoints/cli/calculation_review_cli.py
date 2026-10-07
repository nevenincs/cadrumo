"""Publish an immutable saved calculation review through the profile worker."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.export.calculation_review_xlsx_operation import (
    CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
    CalculationReviewXlsxRequest,
    CalculationReviewXlsxResult,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.json_contract import OutputSchema
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .common import emit_envelope
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


class CalculationReviewWorkbookResult(OutputSchema):
    """Facts of the selected saved review workbook and its published bytes."""

    publication: CalculationReviewXlsxResult


def export_calculation_review_cli(
    ctx: typer.Context,
    calculation_revision_id: str,
    output: Path,
    replace_existing: bool = False,
    *,
    filing_record_id: str | None = None,
    command: str = "modelo.spreadsheet.review",
) -> None:
    """Export a draft or sealed saved calculation as a local review workbook."""
    client = bound_profile_client(ctx)
    request = CalculationReviewXlsxRequest(
        profile_id=client.profile_id,
        calculation_revision_id=calculation_revision_id,
        filing_record_id=filing_record_id,
        output_path=str(output.resolve()),
        replace_existing=replace_existing,
        report_language=OutputLanguage(active_output_language()),
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=CALCULATION_REVIEW_XLSX_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=CalculationReviewXlsxResult,
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
        or result.calculation_revision_id != request.calculation_revision_id
        or result.output_path != request.output_path
    ):
        raise invalid_completion_error(completed)
    emit_envelope(
        ctx,
        command=command,
        result=CalculationReviewWorkbookResult(publication=result),
        lines=(
            f"title\t{result.title}",
            f"output_path\t{result.output_path}",
            f"calculation_state\t{result.calculation_state.value}",
            f"review_status\t{result.review_status.value}",
            f"byte_size\t{result.byte_size}",
        ),
    )
