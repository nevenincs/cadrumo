"""Behavior handler for the root-level modelo export command."""

from __future__ import annotations

import typer

from ...application.modelo.export import ModeloExportResult
from ...application.modelo.export_projection import ModeloExportPublicResultV2
from ...application.modelo.operation_definitions import ModeloExportRequest
from ...application.modelo.operator_inputs import ModeloExportOperatorInput
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ._modelo_cli_support import (
    parse_revision_selector,
    resolve_default_actor,
)
from ._modelo_payloads import ModeloExportPayload
from .common import emit_envelope
from .runtime_modelo_export import run_modelo_export
from .runtime_modelo_verification import select_modelo_work_revision_for_cli


def _local_export_evidence_notice(result: ModeloExportResult) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.export.local_export_not_official_evidence",
        message="The local export is not official filing evidence.",
        context={
            "evidence_status": result.local_evidence_status,
            "modelo": str(result.modelo),
            "filing_year": str(result.filing_year),
            "period": result.period.registry_token,
        },
    )


def _completeness_advisory_notice(result: ModeloExportResult) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.export.completeness_unverified",
        message=result.completeness_advisory_message,
        context={
            "reason": "no_completeness_manifest",
            "modelo": str(result.modelo),
            "filing_year": str(result.filing_year),
            "period": result.period.registry_token,
        },
    )


def _development_software_identity_notice(result: ModeloExportResult) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.export.development_software_identity",
        message=(
            "The file header carries Cadrumo's all-zero development software identity; "
            "AEAT will not accept this file for presentation."
        ),
        context={
            "software_identity_grade": str(result.software_identity_grade),
            "modelo": str(result.modelo),
            "filing_year": str(result.filing_year),
            "period": result.period.registry_token,
        },
    )


def _export_notices(result: ModeloExportResult) -> list[Notice]:
    notices = [_local_export_evidence_notice(result)]
    if result.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK:
        notices.append(_development_software_identity_notice(result))
    if result.completeness_unverified:
        notices.append(_completeness_advisory_notice(result))
    return notices


def _export_text_lines(result: ModeloExportResult) -> list[str]:
    return [
        "operation\tmodelo.export",
        f"work_unit_id\t{result.work_unit_id}",
        f"calculation_revision_id\t{result.calculation_revision_id}",
        f"bucket\t{result.bucket_id}",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period}",
        f"output_path\t{result.output_path}",
        f"byte_size\t{result.byte_size}",
        f"file_sha256\t{result.file_sha256}",
        f"format\t{result.format}",
        f"bucket_event_id\t{result.bucket_event_id}",
        f"evidence_status\t{result.local_evidence_status}",
        f"software_identity_grade\t{result.software_identity_grade or 'none'}",
        f"evidence_notice\t{result.official_evidence_message}",
    ]


__all__ = ["modelo_export_verb"]


def modelo_export_verb(
    ctx: typer.Context,
    **input_values: object,
) -> None:
    """Export a verified-complete or filed modelo revision to disk."""
    operator_input = ModeloExportOperatorInput.model_validate(input_values)
    if (
        operator_input.output is None
        or not str(operator_input.output).strip()
        or str(operator_input.output).strip() == "."
    ):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.export.errors.output_required",
            )
        )
    client, selected_revision = select_modelo_work_revision_for_cli(
        ctx,
        calculation_revision_id=operator_input.revision,
        work_unit_id=operator_input.work_unit_id,
        modelo=operator_input.modelo,
        year=operator_input.year,
        period=operator_input.period,
        revision=operator_input.registry_revision,
        bucket_id=operator_input.bucket_id,
        selector=parse_revision_selector(operator_input.select),
        default_for="export",
    )
    target_revision_id = selected_revision.calculation_revision_id
    completed = run_modelo_export(
        client,
        ModeloExportRequest(
            calculation_revision_id=target_revision_id,
            output_path=str(operator_input.output.resolve()),
            actor=operator_input.actor or resolve_default_actor(),
            refund_election=operator_input.refund_election,
            payment_election=operator_input.payment_election,
            prior_domiciliation_election=operator_input.prior_domiciliation_election,
            replace_existing=operator_input.replace_existing,
        ),
        work_unit_id=selected_revision.unit.work_unit_id,
    )
    if not isinstance(completed.projection, ModeloExportPublicResultV2):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    receipt = completed.projection.fichero_boe
    if receipt is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    result = receipt.to_result()
    export_result = ModeloExportPayload.from_result(result)
    emit_envelope(
        ctx,
        command="modelo.export",
        result=export_result,
        lines=_export_text_lines(result),
        notices=_export_notices(result),
    )


modelo_export_verb.__dict__["__input_model__"] = ModeloExportOperatorInput
