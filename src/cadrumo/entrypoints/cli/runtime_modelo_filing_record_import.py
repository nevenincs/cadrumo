"""CLI transport for worker-owned filing-record imports."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import typer

from ...application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from ...application.modelo.filing_record_import_operation import (
    MODELO_FILING_RECORD_IMPORT_OPERATION_DEFINITION_ID,
    ModeloFilingRecordImportProjection,
    ModeloFilingRecordImportRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from ._filing_chain_payloads import filing_reconciliation_payload
from ._modelo_payloads import FilingRecordImportResult, ModeloRecordPayload
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import run_registered_operation, submitted_operation_error


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
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        )
    try:
        reconciliation = projection.reconciliation.to_result()
        if (
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
                and source_file is None
            )
            or projection.profile_id != client.profile_id
            or projection.record.bucket_id != str(client.profile_id)
            or projection.record.external_evidence is None
            or projection.record.external_evidence.kind is not evidence_kind
            or projection.record.external_evidence.reference_id != evidence_reference_id
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
        if (
            result.bucket_id != str(client.profile_id)
            or result.filing_record_id != reconciliation.filing_record_id
            or result.work_unit_id != projection.record.work_unit_id
            or result.external_evidence is None
        ):
            raise ValueError("filing import CLI projection exceeds its submitted result")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return result


__all__ = ["import_modelo_filing_record"]
