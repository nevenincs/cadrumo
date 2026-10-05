"""The export facts the command line prints are the facts the supervised export result carries.

The terminal interface submits the registered ``modelo.export`` operation and
renders its public result; the command line calls the export service directly
and prints its own envelope. One verified revision is exported through both,
and the operation's result -- resolved through the same composed result door
the terminal interface uses -- must agree with the command line's envelope
field for field: the revision, the format, the software identity grade, the
evidence status, the completeness and the fingerprint of the bytes.

The calculation summary PDF is deterministic for one revision, one signing key
and one export instant, so under one frozen instant the two surfaces must write
the same bytes, and a different instant must not.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend_context
from cadrumo.application.modelo.export_projection import (
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV3,
)
from cadrumo.application.modelo.operation_definitions import MODELO_EXPORT_OPERATION_DEFINITION_ID
from cadrumo.application.modelo.work_export_contracts import ModeloExportRequest
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.core.modelo_export_artefact import ModeloExportArtefact
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.time.clock import frozen_clock
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.filing.software_identity import AeatSoftwareIdentityGrade
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.operation_composition import compose_operation_dependencies
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import build_verified_modelo_303_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_COMPLETENESS_UNVERIFIED_NOTICE = "modelo.export.completeness_unverified"
_NOT_OFFICIAL_EVIDENCE_NOTICE = "modelo.export.local_export_not_official_evidence"
_SUMMARY_EXPORTED_AT = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)
#: A minute later: inside the unlocked session's idle window, which a frozen
#: clock would otherwise run past.
_LATER_SUMMARY_EXPORTED_AT = _SUMMARY_EXPORTED_AT + timedelta(minutes=1)


def _operation_result(
    *,
    work_unit_id: str,
    calculation_revision_id: str,
    output_path: Path,
    operation: PinnedAuthorityOperation,
    artefact: ModeloExportArtefact,
) -> ModeloExportPublicResultV3:
    """Export through the registered operation and resolve its public result as the TUI does."""

    async def run() -> ModeloExportPublicResultV3:
        services = compose_operation_dependencies(authority_operation=operation)
        try:
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
                    subject_ref=work_unit_id,
                    payload=ModeloExportRequest(
                        calculation_revision_id=calculation_revision_id,
                        output_path=str(output_path),
                        actor="operator",
                        artefact=artefact,
                    ),
                ),
                actor_ref="operator:export-result-parity",
            )
            await services.submission.start(submitted.receipt.operation_id)
            await services.submission.settled(submitted.receipt.operation_id)
            observed = await services.observation.observe(
                OperationObservationRequestV1(
                    operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=64
                )
            )
            assert isinstance(observed, OperationObservationSuccessV1)
            projection = observed.projection
            assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, (
                projection.refusal_ref or projection.failure_error_code
            )
            schema = projection.definition_contract.result_schema
            assert schema is not None
            resolved = await services.result.resolve(
                OperationResultProjectionRequestV1(
                    operation_id=projection.operation_id,
                    terminal_revision=projection.revision,
                    definition_contract_digest=projection.definition_contract.definition_contract_digest,
                    result_schema=schema,
                ),
                ModeloExportPublicResultV3,
            )
            assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
            assert isinstance(resolved.projection, ModeloExportPublicResultV3)
            return resolved.projection
        finally:
            await services.shutdown()

    return asyncio.run(run())


def test_the_filing_file_result_states_what_the_command_line_prints(tmp_path: Path) -> None:
    """Revision, format, identity grade, evidence, completeness and fingerprint agree across surfaces."""
    with isolated_backend_context(tmp_path), bundled_indexed_authority().operation() as operation:
        _taxpayer_nif, _bucket_id, verified, *_repositories = build_verified_modelo_303_revision(operation=operation)
        cli_out = tmp_path / "cli-303.txt"
        operation_out = tmp_path / "operation-303.txt"
        cli = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "export",
                "--revision",
                verified.calculation_revision_id,
                "--output",
                str(cli_out),
            ]
        )
        result = _operation_result(
            work_unit_id=verified.work_unit_id,
            calculation_revision_id=verified.calculation_revision_id,
            output_path=operation_out,
            operation=operation,
            artefact=ModeloExportArtefact.FICHERO_BOE,
        )

    assert cli.exit_code == 0, cli.output
    envelope = json.loads(cli.output)
    cli_result = envelope["result"]
    notices = {notice["code"]: notice for notice in envelope["notices"]}

    assert result.artefact is ModeloExportArtefact.FICHERO_BOE
    assert result.calculation_revision_id == cli_result["calculation_revision_id"] == verified.calculation_revision_id
    assert result.export_format == cli_result["format"]
    assert result.software_identity_grade == cli_result["software_identity_grade"]
    # Modelo 303 renders an envelope header, which carries the development identity.
    assert result.software_identity_grade is AeatSoftwareIdentityGrade.DEVELOPMENT_MOCK
    assert result.evidence_status == notices[_NOT_OFFICIAL_EVIDENCE_NOTICE]["context"]["evidence_status"]
    assert result.evidence_status is ModeloExportEvidenceStatus.LOCAL_EXPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE
    # The command line warns only when completeness is unverified; Modelo 303
    # declares a completeness manifest, so neither surface flags it.
    assert _COMPLETENESS_UNVERIFIED_NOTICE not in notices
    assert result.completeness is ModeloExportCompleteness.NOT_FLAGGED
    # Both surfaces wrote the same bytes, so size and digest agree, and each
    # agrees with what is actually on disk at its own path.
    assert result.byte_size == cli_result["byte_size"] == operation_out.stat().st_size
    assert result.file_sha256 == cli_result["file_sha256"] == hashlib.sha256(operation_out.read_bytes()).hexdigest()
    assert result.output_path == str(operation_out)
    assert cli_result["output_path"] == str(cli_out)


def test_the_calculation_report_result_states_what_the_command_line_prints(tmp_path: Path) -> None:
    """A report states its format and identity grade as the command line does, and claims no completeness."""
    with isolated_backend_context(tmp_path), bundled_indexed_authority().operation() as operation:
        _taxpayer_nif, _bucket_id, verified, *_repositories = build_verified_modelo_303_revision(operation=operation)
        cli_out = tmp_path / "cli-303-report.csv"
        operation_out = tmp_path / "operation-303-report.csv"
        cli = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "work",
                "report",
                verified.work_unit_id,
                "--output",
                str(cli_out),
            ]
        )
        result = _operation_result(
            work_unit_id=verified.work_unit_id,
            calculation_revision_id=verified.calculation_revision_id,
            output_path=operation_out,
            operation=operation,
            artefact=ModeloExportArtefact.CALCULATION_REPORT_CSV,
        )

    assert cli.exit_code == 0, cli.output
    cli_result = json.loads(cli.output)["result"]

    assert result.artefact is ModeloExportArtefact.CALCULATION_REPORT_CSV
    assert result.calculation_revision_id == cli_result["calculation_revision_id"] == verified.calculation_revision_id
    assert result.export_format == cli_result["document_format"] == "csv"
    assert result.software_identity_grade == cli_result["software_identity_grade"]
    assert result.evidence_status is (
        ModeloExportEvidenceStatus.LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE
    )
    assert result.completeness is ModeloExportCompleteness.NOT_ASSESSED
    # Each report carries its own export timestamp, so the two files differ;
    # each fingerprint is checked against its own bytes.
    assert result.byte_size == operation_out.stat().st_size
    assert result.file_sha256 == hashlib.sha256(operation_out.read_bytes()).hexdigest()
    assert cli_result["file_sha256"] == hashlib.sha256(cli_out.read_bytes()).hexdigest()


def test_the_calculation_summary_pdf_is_byte_identical_from_either_surface(tmp_path: Path) -> None:
    """One revision exported at one instant is one summary, whichever surface wrote it."""
    with isolated_backend_context(tmp_path), bundled_indexed_authority().operation() as operation:
        _taxpayer_nif, _bucket_id, verified, *_repositories = build_verified_modelo_303_revision(operation=operation)
        cli_out = tmp_path / "cli-303-summary.pdf"
        operation_out = tmp_path / "operation-303-summary.pdf"
        later_out = tmp_path / "operation-303-summary-later.pdf"
        with frozen_clock(_SUMMARY_EXPORTED_AT):
            cli = invoke_cached_cli(
                [
                    "--format",
                    "json",
                    "app",
                    "modelo",
                    "work",
                    "report",
                    verified.work_unit_id,
                    "--document-format",
                    "pdf",
                    "--output",
                    str(cli_out),
                ]
            )
            result = _operation_result(
                work_unit_id=verified.work_unit_id,
                calculation_revision_id=verified.calculation_revision_id,
                output_path=operation_out,
                operation=operation,
                artefact=ModeloExportArtefact.CALCULATION_REPORT_PDF,
            )
        with frozen_clock(_LATER_SUMMARY_EXPORTED_AT):
            later = _operation_result(
                work_unit_id=verified.work_unit_id,
                calculation_revision_id=verified.calculation_revision_id,
                output_path=later_out,
                operation=operation,
                artefact=ModeloExportArtefact.CALCULATION_REPORT_PDF,
            )

    assert cli.exit_code == 0, cli.output
    cli_result = json.loads(cli.output)["result"]
    cli_bytes = cli_out.read_bytes()
    operation_bytes = operation_out.read_bytes()

    assert cli_bytes.startswith(b"%PDF-")
    assert operation_bytes == cli_bytes
    assert result.artefact is ModeloExportArtefact.CALCULATION_REPORT_PDF
    assert result.calculation_revision_id == cli_result["calculation_revision_id"] == verified.calculation_revision_id
    assert result.export_format == cli_result["document_format"] == "pdf"
    assert result.software_identity_grade == cli_result["software_identity_grade"]
    assert result.evidence_status is (
        ModeloExportEvidenceStatus.LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE
    )
    assert result.completeness is ModeloExportCompleteness.NOT_ASSESSED
    assert result.byte_size == cli_result["byte_size"] == len(cli_bytes)
    assert result.file_sha256 == cli_result["file_sha256"] == hashlib.sha256(cli_bytes).hexdigest()
    # The equality above is a statement about the inputs, not an artefact of
    # comparing two copies of one thing: the export instant is one of those
    # inputs, and moving it changes the bytes.
    assert later.file_sha256 == hashlib.sha256(later_out.read_bytes()).hexdigest() != result.file_sha256
