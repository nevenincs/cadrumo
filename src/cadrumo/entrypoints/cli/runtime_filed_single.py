"""CLI bridge for one exact-profile registered filed capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import typer

from ...application.live.filed_single_capture_operation import (
    FILED_SINGLE_CAPTURE_DEFINITION_ID,
    FiledCaptureNoticeV1,
    FiledReconciliationNoticeV1,
    FiledReconciliationV1,
    FiledSingleCapturePublicResultV1,
    FiledSingleCaptureRequest,
)
from ...application.live.remote_state_models import FiledDataCaptureReport
from ...application.modelo.filing_chain_reconciliation import (
    FilingEvidenceBasis,
    FilingReconciliationNotice,
    FilingReconciliationNoticeCode,
    FilingReconciliationOutcome,
    FilingReconciliationResult,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...core.bucket_pointer import require_active_bucket_id
from ...core.casilla_id import validated_casilla_id
from ...core.json_contract import Notice
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from .runtime_profile_binding import require_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


@dataclass(frozen=True, slots=True)
class FiledSingleCaptureRead:
    """Keep the settled worker receipt with the restored CLI report."""

    completion: RegisteredOperationCompletion[FiledSingleCapturePublicResultV1]
    report: FiledDataCaptureReport


def _context(pairs: tuple[tuple[str, str], ...] | None) -> dict[str, str] | None:
    if pairs is None:
        return None
    context = dict(pairs)
    if len(context) != len(pairs):
        raise ValueError("filed-capture context contains duplicate keys")
    return context


def _capture_notice(notice: FiledCaptureNoticeV1) -> Notice:
    return Notice(
        severity=notice.severity,
        code=notice.code,
        message=notice.message,
        context=_context(notice.context),
    )


def _reconciliation(
    row: FiledReconciliationV1,
    *,
    profile_id: UUID,
    request: FiledSingleCaptureRequest,
) -> FilingReconciliationResult:
    if row.bucket_id != str(profile_id) or row.modelo != request.modelo or row.filing_year != request.year:
        raise ValueError("filed-capture reconciliation does not match its profile pair")
    period = Period.from_year_and_code(row.filing_year, row.period)
    if request.period is not None and period != Period.from_year_and_code(request.year, request.period):
        raise ValueError("filed-capture reconciliation does not match its requested period")
    basis: FilingEvidenceBasis | None
    if row.evidence_basis == "casillas":
        basis = "casillas"
    elif row.evidence_basis == "receipt_totals":
        basis = "receipt_totals"
    elif row.evidence_basis is None:
        basis = None
    else:
        raise ValueError("filed-capture reconciliation has an unknown evidence basis")
    return FilingReconciliationResult(
        outcome=FilingReconciliationOutcome(row.outcome),
        bucket_id=row.bucket_id,
        modelo=row.modelo,
        filing_year=row.filing_year,
        period=period,
        member_nif=row.member_nif,
        filing_record_id=row.filing_record_id,
        affected_filing_record_ids=row.affected_filing_record_ids,
        differing_casilla_ids=tuple(validated_casilla_id(value) for value in row.differing_casilla_ids),
        evidence_basis=basis,
        notices=tuple(_reconciliation_notice(notice) for notice in row.notices),
    )


def _reconciliation_notice(notice: FiledReconciliationNoticeV1) -> FilingReconciliationNotice:
    return FilingReconciliationNotice(
        code=FilingReconciliationNoticeCode(notice.code),
        context=_context(notice.context) or {},
    )


def _presentation_report(
    projection: FiledSingleCapturePublicResultV1,
    *,
    profile_id: UUID,
    request: FiledSingleCaptureRequest,
) -> FiledDataCaptureReport:
    """Restore the existing renderer report from its safe public projection."""
    if (
        projection.output_root != str(request.output_root)
        or projection.modelo != request.modelo
        or projection.year != request.year
    ):
        raise ValueError("filed-capture result does not match its submitted pair")
    reconciliations = tuple(
        _reconciliation(row, profile_id=profile_id, request=request) for row in projection.reconciliations
    )
    return FiledDataCaptureReport(
        output_root=projection.output_root,
        modelo=projection.modelo,
        year=projection.year,
        captured_count=projection.captured_count,
        reached_count=projection.reached_count,
        observation_paths=projection.observation_paths,
        artefact_refs=projection.artefact_refs,
        justificante_metadata_count=projection.justificante_metadata_count,
        justificante_csvs=projection.justificante_csvs,
        filing_evidence_stamped_count=projection.filing_evidence_stamped_count,
        filing_record_ids=projection.filing_record_ids,
        filing_evidence_conflict_count=projection.filing_evidence_conflict_count,
        filing_evidence_conflict_record_ids=projection.filing_evidence_conflict_record_ids,
        evidence_notices=tuple(_capture_notice(notice) for notice in projection.evidence_notices),
        casilla_count=projection.casilla_count,
        calculation_observation_count=projection.calculation_observation_count,
        calculation_observation_keys=projection.calculation_observation_keys,
        reconciliation_results=reconciliations,
    )


def _settled_effect(report: FiledDataCaptureReport) -> OperationEffect:
    return (
        OperationEffect.UPDATED
        if report.captured_count or report.calculation_observation_count or report.filing_evidence_stamped_count
        else OperationEffect.NONE
    )


def read_filed_single_capture_for_cli(
    ctx: typer.Context,
    *,
    modelo: str,
    year: int,
    output_root: Path,
    period: Period | None,
    expediente_id: str | None,
    limit: int | None,
) -> FiledSingleCaptureRead:
    """Submit one capture and accept only its exact-profile settled result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = FiledSingleCaptureRequest(
        profile_id=profile_id,
        output_root=output_root,
        modelo=modelo,
        year=year,
        period=period.registry_token if period is not None else None,
        expediente_id=expediente_id,
        limit=limit,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=FILED_SINGLE_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=FiledSingleCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        if not isinstance(completed.projection, FiledSingleCapturePublicResultV1):
            raise ValueError("filed-capture result projection has an invalid type")
        report = _presentation_report(completed.projection, profile_id=profile_id, request=request)
        expected_effect = _settled_effect(report)
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or (
                completed.effect is not expected_effect
                and not (expected_effect is OperationEffect.NONE and completed.effect is OperationEffect.UPDATED)
            )
        ):
            raise ValueError("filed-capture result disagrees with its settled receipt")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return FiledSingleCaptureRead(completion=completed, report=report)


__all__ = ["FiledSingleCaptureRead", "read_filed_single_capture_for_cli"]
