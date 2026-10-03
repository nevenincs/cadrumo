"""Behavior for the modelo work calculation-report surface.

``work report`` addresses a work target exactly as ``work review`` does and
publishes that target's current revision as a calculation report. Only the
address, the document format, the report language and the destination are decided
here; what the report contains and where its bytes land are the application
service's. The summary PDF is refused before any profile state is read when its
optional extra is absent.

``work report-verify`` checks a calculation summary PDF: the document alone with
``--document-only``, and otherwise traced to the active profile's encrypted store
as well. It exits non-zero whenever the verdict is a refusal.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

import typer

from ...application.modelo.calculation_report_document import require_calculation_summary_pdf_available
from ...application.modelo.calculation_report_export import (
    ModeloCalculationReportResult,
)
from ...application.modelo.calculation_report_verification import (
    CalculationSummaryVerification,
    CalculationSummaryVerificationOutcome,
    verify_calculation_summary,
)
from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.external_constants import OutputLanguage
from ...core.hashing import hash_file
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.filing.software_identity import AeatSoftwareIdentityGrade
from ._modelo_cli_support import validate_trusted_public_key
from ._modelo_payloads import WorkReportResult, WorkReportVerifyResult
from .common import activate_subcommand_output_language, emit_envelope
from .registered_operation_errors import invalid_completion_error

__all__ = ["work_report", "work_report_verify"]


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
        f"signing_key_fingerprint\t{result.signing_key_fingerprint or ''}",
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
    if document_format is CalculationReportDocumentFormat.PDF:
        # Refused before the store is opened, as its own registered refusal: an
        # installation that cannot write the summary learns so, and how to fix
        # it, before any figure is read.
        require_calculation_summary_pdf_available()
    from ...application.modelo.operation_definitions import ModeloExportRequest
    from ...application.modelo.selectors import ModeloCalculationRevisionSelector
    from ...core.modelo_export_artefact import ModeloExportArtefact
    from ._modelo_cli_support import resolve_default_actor
    from .runtime_modelo_export import run_modelo_export
    from .runtime_modelo_verification import select_modelo_work_revision_for_cli

    client, selection = select_modelo_work_revision_for_cli(
        ctx,
        calculation_revision_id=None,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        selector=ModeloCalculationRevisionSelector.CURRENT,
        default_for=None,
    )
    artefact = {
        CalculationReportDocumentFormat.CSV: ModeloExportArtefact.CALCULATION_REPORT_CSV,
        CalculationReportDocumentFormat.PDF: ModeloExportArtefact.CALCULATION_REPORT_PDF,
    }[document_format]
    completed = run_modelo_export(
        client,
        ModeloExportRequest(
            calculation_revision_id=selection.calculation_revision_id,
            output_path=str(output.resolve()),
            artefact=artefact,
            report_language=OutputLanguage(active_output_language()),
            replace_existing=replace_existing,
            actor=resolve_default_actor(),
        ),
        work_unit_id=selection.unit.work_unit_id,
    )
    receipt = completed.projection.calculation_report
    if receipt is None:
        raise invalid_completion_error(completed)
    result = receipt.to_result()
    emit_envelope(
        ctx,
        command="modelo.work.report",
        result=WorkReportResult.from_result(result),
        lines=_report_lines(result),
        notices=_report_notices(result),
    )


def _verify_lines(verification: CalculationSummaryVerification, path: Path) -> list[str]:
    lines = [
        "operation\tmodelo.work.report_verify",
        f"path\t{path}",
        f"outcome\t{verification.outcome.value}",
        f"store_checked\t{verification.store_checked}",
        f"calculation_revision_id\t{verification.calculation_revision_id or ''}",
        f"report_sha256\t{verification.report_sha256 or ''}",
        f"statement_sha256\t{verification.statement_sha256 or ''}",
        f"signing_key_fingerprint\t{verification.signing_key_fingerprint or ''}",
    ]
    lines.extend(
        "\t".join(
            (
                "check",
                check.layer.value,
                check.check.value,
                "ok" if check.reason is None else check.reason.value,
                check.detail or "",
            ),
        )
        for check in verification.checks
    )
    return lines


_VERIFY_NOTICE_LOCALE_KEYS: Final[Mapping[CalculationSummaryVerificationOutcome, str]] = MappingProxyType(
    {
        CalculationSummaryVerificationOutcome.VERIFIED_WITH_LATER_CHANGES: (
            "cli.app.modelo.work.report_verify.later_changes"
        ),
        CalculationSummaryVerificationOutcome.VALID_UNPINNED: "cli.app.modelo.work.report_verify.unpinned",
        CalculationSummaryVerificationOutcome.REFUSED: "cli.app.modelo.work.report_verify.refused",
    },
)
"""The notice each verdict short of ``verified`` carries, saying what it does not establish."""


def _verify_notices(verification: CalculationSummaryVerification) -> list[Notice]:
    """Say what the verdict does and does not establish."""
    outcome = verification.outcome
    key = _VERIFY_NOTICE_LOCALE_KEYS.get(outcome)
    if key is None:
        return []
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=f"modelo.work.report_verify.{outcome.value}",
            message=tr(key),
            context={
                "outcome": outcome.value,
                "reasons": ",".join(reason.value for reason in verification.reasons),
            },
        ),
    ]


def work_report_verify(
    ctx: typer.Context,
    path: Path,
    trusted_key: str | None = None,
    document_only: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """Verify a calculation summary PDF, and trace it to the active profile's store."""
    activate_subcommand_output_language(ctx, output_language)
    trusted_public_key_hex = validate_trusted_public_key(trusted_key)
    if not path.is_file():
        raise typer.BadParameter(tr("cli.app.modelo.work.report_verify.errors.file_not_found", path=str(path)))
    if document_only:
        from ...adapters.outbound.calculation_summary_pdf.summary_reading import read_calculation_summary_pdf

        verification = verify_calculation_summary(
            path.read_bytes(),
            reader=read_calculation_summary_pdf,
            trusted_public_key_hex=trusted_public_key_hex,
        )
    else:
        from ...application.modelo.calculation_report_verification_operation import (
            ModeloCalculationReportVerificationRequest,
        )
        from .runtime_modelo_calculation_report_verify import run_modelo_calculation_report_verify
        from .runtime_profile_binding import bound_profile_client

        client = bound_profile_client(ctx)
        source_path = path.resolve()
        source_sha256, _ = hash_file(source_path)
        completed = run_modelo_calculation_report_verify(
            client,
            ModeloCalculationReportVerificationRequest(
                profile_id=client.profile_id,
                source_path=str(source_path),
                source_sha256=source_sha256,
                trusted_public_key_hex=trusted_public_key_hex,
            ),
        )
        verification = completed.projection.verification.to_verification()
    emit_envelope(
        ctx,
        command="modelo.work.report_verify",
        result=WorkReportVerifyResult.from_verification(verification, path=path),
        lines=_verify_lines(verification, path),
        notices=_verify_notices(verification),
    )
    if verification.outcome is CalculationSummaryVerificationOutcome.REFUSED:
        raise typer.Exit(code=1)
