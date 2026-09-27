"""Behavior for the modelo work calculation-report surface.

The verb addresses a work target exactly as ``work review`` does and publishes
that target's current revision as a calculation report. Only the address, the
document format, the report language and the destination are decided here; what
the report contains and where its bytes land are the application service's.
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo.action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    WorkUnitNotFoundError,
)
from ...application.modelo.calculation_report_export import (
    ModeloCalculationReportCommand,
    ModeloCalculationReportResult,
    ModeloCalculationReportTaxpayerUnknownError,
    export_modelo_calculation_report,
)
from ...application.modelo.export import (
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
)
from ...application.modelo.export_sink import ModeloExportOutputPathError
from ...application.workflow.persistence import workflow_state_repository
from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ._modelo_behavior_support import require_active_profile, resolve_work_unit_for_cli
from ._modelo_cli_support import bad_parameter_from_error, resolve_explicit_or_active_bucket_id
from ._modelo_payloads import WorkReportResult
from .common import activate_subcommand_output_language, emit_envelope, filing_taxpayer_or_refuse
from .state_projection_support import (
    authority_operation,
    modelo_export_ports_factory,
    review_package_signing_keypair_capability_factory,
)

__all__ = ["work_report"]


def _report_lines(result: ModeloCalculationReportResult) -> list[str]:
    return [
        "operation\tmodelo.work.report",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period.registry_token}",
        f"work_unit_id\t{result.work_unit_id}",
        f"calculation_revision_id\t{result.calculation_revision_id}",
        f"verification_report_id\t{result.verification_report_id or ''}",
        f"filing_record_id\t{result.filing_record_id or ''}",
        f"document_format\t{result.document_format.value}",
        f"report_language\t{result.report_language.value}",
        f"output_path\t{result.output_path}",
        f"byte_size\t{result.byte_size}",
        f"file_sha256\t{result.file_sha256}",
        f"report_sha256\t{result.report_sha256}",
        f"row_count\t{result.row_count}",
        f"software_identity_grade\t{result.software_identity_grade or 'none'}",
        f"evidence_notice\t{result.local_calculation_notice}",
    ]


def _report_notices(result: ModeloCalculationReportResult) -> list[Notice]:
    """Say what the artefact is, and say when its modelo's filing file is unpresentable."""
    notices = [
        Notice(
            severity=NoticeSeverity.WARNING,
            code="modelo.work.report.local_calculation_not_official_evidence",
            message=result.local_calculation_notice,
            context={
                "modelo": str(result.modelo),
                "filing_year": str(result.filing_year),
                "period": result.period.registry_token,
                "document_format": result.document_format.value,
            },
        ),
    ]
    if result.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="modelo.work.report.development_software_identity",
                message=tr("cli.app.modelo.work.report.development_software_identity"),
                context={
                    "software_identity_grade": str(result.software_identity_grade),
                    "modelo": str(result.modelo),
                    "filing_year": str(result.filing_year),
                    "period": result.period.registry_token,
                },
            ),
        )
    return notices


def work_report(
    ctx: typer.Context,
    output: Path,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    document_format: CalculationReportDocumentFormat = CalculationReportDocumentFormat.CSV,
    replace_existing: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Publish the addressed work target's sealed revision as a calculation report."""
    activate_subcommand_output_language(ctx, output_language)
    require_active_profile()
    # An unusable destination -- blank, an existing directory, a missing parent,
    # an occupied path -- is the export sink's refusal, raised before any
    # taxpayer figure is assembled. Restating it here would be a second
    # admission rule for the same question.
    unit = resolve_work_unit_for_cli(
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    if unit.current_calculation_revision_id is None:
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.work.report.errors.calculation_required",
                work_unit_id=unit.work_unit_id,
                modelo=str(unit.modelo),
            ),
        )
    workflow_profile = filing_taxpayer_or_refuse(workflow_state_repository().load())
    resolved_bucket_id = resolve_explicit_or_active_bucket_id(bucket_id)
    try:
        result = export_modelo_calculation_report(
            ModeloCalculationReportCommand(
                calculation_revision_id=unit.current_calculation_revision_id,
                document_format=document_format,
                # The report's language is the language this invocation renders
                # in, resolved once here so the artefact and the messages about
                # it cannot be in two different languages.
                report_language=OutputLanguage(active_output_language()),
                output_path=output,
                replace_existing=replace_existing,
            ),
            export_ports=modelo_export_ports_factory(ctx)(
                bucket_id=resolved_bucket_id,
                m303_rectificativa_taxpayer_tax_id=workflow_profile.tax_id,
            ),
            signing_keypair=review_package_signing_keypair_capability_factory(ctx)(bucket_id=resolved_bucket_id),
            operation=authority_operation(ctx),
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        ModeloCalculationReportTaxpayerUnknownError,
        ModeloExportCrossBucketRefusedError,
        ModeloExportNoActiveBucketError,
        ModeloExportOutputPathError,
        WorkUnitNotFoundError,
    ) as exc:
        raise bad_parameter_from_error(exc) from exc
    emit_envelope(
        ctx,
        command="modelo.work.report",
        result=WorkReportResult.from_result(result),
        lines=_report_lines(result),
        notices=_report_notices(result),
    )
