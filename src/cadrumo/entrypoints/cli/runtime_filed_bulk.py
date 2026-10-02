"""CLI bridge for an exact-profile registered bulk filed capture."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import typer

from ...application.live.filed_bulk_capture_operation import (
    FILED_BULK_CAPTURE_DEFINITION_ID,
    FiledBulkCapturePublicResultV1,
    FiledBulkCaptureRequest,
)
from ...application.live.remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCasillaSkipRow,
    FiledDataCaptureFailureRow,
)
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
class FiledBulkCaptureRead:
    """Keep the correlated receipt beside the restored presentation report."""

    completion: RegisteredOperationCompletion[FiledBulkCapturePublicResultV1]
    report: BulkFiledDataCaptureReport


def _context(pairs: tuple[tuple[str, str], ...] | None) -> dict[str, str] | None:
    if pairs is None:
        return None
    context = dict(pairs)
    if len(context) != len(pairs):
        raise ValueError("filed-bulk notice context contains duplicate keys")
    return context


def _notice(row: object) -> Notice:
    from ...application.live.filed_single_capture_operation import FiledCaptureNoticeV1

    if not isinstance(row, FiledCaptureNoticeV1):
        raise ValueError("filed-bulk notice has an invalid type")
    return Notice(severity=row.severity, code=row.code, message=row.message, context=_context(row.context))


def _reconciliation(row: object, *, profile_id: UUID, request: FiledBulkCaptureRequest) -> FilingReconciliationResult:
    from ...application.live.filed_single_capture_operation import FiledReconciliationV1

    if not isinstance(row, FiledReconciliationV1):
        raise ValueError("filed-bulk reconciliation has an invalid type")
    if row.bucket_id != str(profile_id) or not (request.year_from <= row.filing_year <= request.year_to):
        raise ValueError("filed-bulk reconciliation is outside the submitted scope")
    if request.modelos is not None and row.modelo not in request.modelos:
        raise ValueError("filed-bulk reconciliation has an unrequested modelo")
    basis: FilingEvidenceBasis | None
    if row.evidence_basis == "casillas":
        basis = "casillas"
    elif row.evidence_basis == "receipt_totals":
        basis = "receipt_totals"
    elif row.evidence_basis is None:
        basis = None
    else:
        raise ValueError("filed-bulk reconciliation has an unknown evidence basis")
    return FilingReconciliationResult(
        outcome=FilingReconciliationOutcome(row.outcome),
        bucket_id=row.bucket_id,
        modelo=row.modelo,
        filing_year=row.filing_year,
        period=Period.from_year_and_code(row.filing_year, row.period),
        member_nif=row.member_nif,
        filing_record_id=row.filing_record_id,
        affected_filing_record_ids=row.affected_filing_record_ids,
        differing_casilla_ids=tuple(validated_casilla_id(value) for value in row.differing_casilla_ids),
        evidence_basis=basis,
        notices=tuple(
            FilingReconciliationNotice(
                code=FilingReconciliationNoticeCode(notice.code),
                context=_context(notice.context) or {},
            )
            for notice in row.notices
        ),
    )


def _presentation_report(
    projection: FiledBulkCapturePublicResultV1, *, profile_id: UUID, request: FiledBulkCaptureRequest
) -> BulkFiledDataCaptureReport:
    """Validate scope and restore canonical report types for CLI rendering."""
    if (
        projection.output_root != str(request.output_root)
        or projection.year_from != request.year_from
        or projection.year_to != request.year_to
        or projection.dry_run != request.dry_run
        or (request.modelos is not None and projection.modelos != request.modelos)
        or projection.failed_count != len(projection.failures)
    ):
        raise ValueError("filed-bulk result does not match its submitted scope")
    for row in (*projection.failures, *projection.skipped_casillas):
        if not (request.year_from <= row.year <= request.year_to) or (
            request.modelos is not None and row.modelo not in request.modelos
        ):
            raise ValueError("filed-bulk detail row is outside the submitted scope")
    report = BulkFiledDataCaptureReport(
        output_root=projection.output_root,
        modelos=projection.modelos,
        pair_outcomes=projection.pair_outcomes,
        year_from=projection.year_from,
        year_to=projection.year_to,
        dry_run=projection.dry_run,
        captured_count=projection.captured_count,
        reached_count=projection.reached_count,
        failed_count=projection.failed_count,
        sync_run_ref=projection.sync_run_ref,
        observation_paths=projection.observation_paths,
        artefact_refs=projection.artefact_refs,
        justificante_metadata_count=projection.justificante_metadata_count,
        justificante_csvs=projection.justificante_csvs,
        filing_evidence_stamped_count=projection.filing_evidence_stamped_count,
        filing_record_ids=projection.filing_record_ids,
        filing_evidence_conflict_count=projection.filing_evidence_conflict_count,
        filing_evidence_conflict_record_ids=projection.filing_evidence_conflict_record_ids,
        casilla_count=projection.casilla_count,
        calculation_observation_count=projection.calculation_observation_count,
        calculation_observation_keys=projection.calculation_observation_keys,
        evidence_notices=tuple(_notice(row) for row in projection.evidence_notices),
        reconciliation_results=tuple(
            _reconciliation(row, profile_id=profile_id, request=request) for row in projection.reconciliations
        ),
        failures=tuple(
            FiledDataCaptureFailureRow(
                modelo=row.modelo,
                year=row.year,
                period=Period.from_year_and_code(row.year, row.period) if row.period is not None else None,
                expediente_id=row.expediente_id,
                error_type=row.error_type,
                message=row.message,
            )
            for row in projection.failures
        ),
        skipped_casillas=tuple(
            FiledCasillaSkipRow(
                modelo=row.modelo,
                year=row.year,
                period=Period.from_year_and_code(row.year, row.period) if row.period is not None else None,
                expediente_id=row.expediente_id,
                casilla_id=row.casilla_id,
                label=row.label,
                value_kind=row.value_kind,
                reason=row.reason,
            )
            for row in projection.skipped_casillas
        ),
        recapture_notices=tuple(_notice(row) for row in projection.recapture_notices),
    )

    report.require_consistent()
    return report


def read_filed_bulk_capture_for_cli(
    ctx: typer.Context,
    *,
    output_root: Path,
    year_from: int,
    year_to: int,
    modelos: tuple[str, ...] | None,
    limit: int | None,
    dry_run: bool,
) -> FiledBulkCaptureRead:
    """Submit the bulk sweep and accept only its correlated settled result."""
    profile_id = UUID(require_active_bucket_id())
    client = require_profile_client(ctx, expected_profile_id=profile_id)
    request = FiledBulkCaptureRequest(
        profile_id=profile_id,
        output_root=output_root,
        year_from=year_from,
        year_to=year_to,
        modelos=modelos,
        limit=limit,
        dry_run=dry_run,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=FILED_BULK_CAPTURE_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=FiledBulkCapturePublicResultV1,
        request_version=1,
        result_version=1,
        timeout=120,
    )
    try:
        if not isinstance(completed.projection, FiledBulkCapturePublicResultV1):
            raise ValueError("filed-bulk result projection has an invalid type")
        report = _presentation_report(completed.projection, profile_id=profile_id, request=request)
        expected_effect = OperationEffect.UPDATED if report.sync_run_ref is not None else OperationEffect.NONE
        # A provider session refresh can persist even when capture itself writes nothing.
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or (
                completed.effect is not expected_effect
                and not (expected_effect is OperationEffect.NONE and completed.effect is OperationEffect.UPDATED)
            )
        ):
            raise ValueError("filed-bulk result disagrees with its settled receipt")
    except Exception:
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=completed.terminal_condition,
            effect=completed.effect,
            refusal_code=completed.refusal_code,
        ) from None
    return FiledBulkCaptureRead(completion=completed, report=report)


__all__ = ["FiledBulkCaptureRead", "read_filed_bulk_capture_for_cli"]
