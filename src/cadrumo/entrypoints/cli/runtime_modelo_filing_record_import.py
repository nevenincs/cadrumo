"""CLI transport for worker-owned filing-record imports."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import typer

from ...application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome, FilingReconciliationResult
from ...application.modelo.filing_record_import_contracts import (
    MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
    ModeloFilingRecordImportProjection,
    ModeloFilingRecordImportRequest,
)
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from ._filing_chain_payloads import filing_reconciliation_payload
from ._modelo_payloads import FilingRecordImportResult, ModeloRecordPayload
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation


def import_modelo_filing_record(
    ctx: typer.Context,
    *,
    work_unit_id: str,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str,
    declared_kind: FilingDeclarationKind | None,
    casilla_values: Mapping[CasillaId, Decimal] | None = None,
    source_file: Path | None = None,
) -> FilingRecordImportResult:
    """Submit exactly one local input mode and restore the established CLI result."""
    if (source_file is not None) == (casilla_values is not None):
        raise typer.BadParameter("filing-record import accepts either a spreadsheet or casilla values")
    if source_file is None and not casilla_values:
        raise typer.BadParameter("filing-record import requires casilla values or a spreadsheet")
    direct_values = tuple(
        sorted(
            (validated_casilla_id(key, surface="filing record import"), format(value, "f"))
            for key, value in (casilla_values or {}).items()
        )
    )

    client = bound_profile_client(ctx)
    source_path = str(source_file.resolve()) if source_file is not None else None
    request = ModeloFilingRecordImportRequest(
        profile_id=client.profile_id,
        work_unit_id=work_unit_id,
        evidence_kind=evidence_kind,
        evidence_reference_id=evidence_reference_id,
        declared_kind=declared_kind,
        actor=actor,
        casilla_values=direct_values,
        source_path=source_path,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloFilingRecordImportProjection,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    projection = completed.projection
    if not isinstance(projection, ModeloFilingRecordImportProjection):
        raise invalid_completion_error(completed)
    return _project_filing_import_result(
        completed, projection, client.profile_id, source_file, evidence_kind, evidence_reference_id
    )


__all__ = ["import_modelo_filing_record"]


def _filing_import_terminal_invalid(
    completed: RegisteredOperationCompletion[ModeloFilingRecordImportProjection],
    reconciliation: FilingReconciliationResult,
    source_file: Path | None,
) -> bool:
    """Correlate imported or already-recorded reconciliation with its effects."""
    return (
        completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or completed.refusal_code is not None
        or completed.effect not in {OperationEffect.NONE, OperationEffect.UPDATED}
        or (
            completed.effect is OperationEffect.NONE
            and reconciliation.outcome is not FilingReconciliationOutcome.ALREADY_RECORDED
        )
        or (
            completed.effect is OperationEffect.UPDATED
            and reconciliation.outcome is FilingReconciliationOutcome.ALREADY_RECORDED
            and (source_file is None)
        )
    )


def _project_filing_import_result(
    completed: RegisteredOperationCompletion[ModeloFilingRecordImportProjection],
    projection: ModeloFilingRecordImportProjection,
    profile_id: UUID,
    source_file: Path | None,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
) -> FilingRecordImportResult:
    """Correlate filing import before adapting its bounded existing CLI payload."""
    try:
        reconciliation = projection.reconciliation.to_result()
        if (
            _filing_import_terminal_invalid(completed, reconciliation, source_file)
            or projection.profile_id != profile_id
            or projection.record.bucket_id != str(profile_id)
            or projection.record.external_evidence is None
            or (projection.record.external_evidence.kind is not evidence_kind)
            or (projection.record.external_evidence.reference_id != evidence_reference_id)
        ):
            raise ValueError("filing import receipt or profile does not match its request")
        record = ModeloRecordPayload.model_validate(
            projection.record.model_dump(mode="python")
            | {
                "period": Period.from_year_and_code(
                    projection.record.filing_year,
                    projection.record.period,
                )
            }
        )
        result = FilingRecordImportResult.model_validate(
            {
                **record.model_dump(mode="python"),
                "reconciliation": filing_reconciliation_payload(reconciliation),
            }
        )
        if _filing_import_cli_payload_mismatch(result, profile_id, reconciliation, projection):
            raise ValueError("filing import CLI projection exceeds its submitted result")
    except Exception:
        raise invalid_completion_error(completed) from None
    return result


def _filing_import_cli_payload_mismatch(
    result: FilingRecordImportResult,
    profile_id: UUID,
    reconciliation: FilingReconciliationResult,
    projection: ModeloFilingRecordImportProjection,
) -> bool:
    """Correlate the CLI adaptation with its admitted record and reconciliation."""
    return (
        result.bucket_id != str(profile_id)
        or result.filing_record_id != reconciliation.filing_record_id
        or result.work_unit_id != projection.record.work_unit_id
        or (result.external_evidence is None)
    )
