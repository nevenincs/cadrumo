"""CLI bridge for worker-owned, exact-profile filing-record listings."""

from __future__ import annotations

import typer

from ...adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ...application.modelo.filing_record_list_operation import (
    MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
    ModeloFilingRecordListEntryProjection,
    ModeloFilingRecordListProjection,
    ModeloFilingRecordListRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode
from ...application.user_profile.access_contracts import AccessDenialCode
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.period import Period
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.filing_record import AeatConfirmationState, ModeloRecordStatus
from ._filing_chain_payloads import AeatRegisterRefPayload
from ._modelo_payloads import ExternalEvidencePayload, ModeloRecordPayload
from .errors import CliRefusedBoundaryError
from .runtime_profile_binding import bound_profile_client
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def _payload_from_projection_row(row: ModeloFilingRecordListEntryProjection) -> ModeloRecordPayload:
    """Adapt the allowlisted worker row to the existing CLI result schema."""
    evidence = row.external_evidence
    register = row.aeat_register
    return ModeloRecordPayload(
        filing_record_id=row.filing_record_id,
        work_unit_id=row.work_unit_id,
        calculation_revision_id=row.calculation_revision_id,
        bucket_id=row.bucket_id,
        modelo=ModeloCode(str(row.modelo)),
        filing_year=row.filing_year,
        period=Period.from_year_and_code(row.filing_year, row.period),
        filed_at=row.filed_at,
        filed_by=row.filed_by,
        member_nif=row.member_nif,
        notes=row.notes,
        origin=row.origin,
        confirmation=row.confirmation,
        declaration_kind=row.declaration_kind,
        aeat_register=(
            AeatRegisterRefPayload(
                expediente_id=register.expediente_id,
                csv=register.csv,
                justificante_number=register.justificante_number,
                tipo_solicitud=register.tipo_solicitud,
                presented_at=register.presented_at,
            )
            if register is not None
            else None
        ),
        aeat_accepted=row.aeat_accepted,
        status=row.status,
        superseded_at=row.superseded_at,
        superseded_by_filing_record_id=row.superseded_by_filing_record_id,
        external_evidence=(
            ExternalEvidencePayload(
                kind=evidence.kind,
                reference_id=evidence.reference_id,
                imported_at=evidence.imported_at,
            )
            if evidence is not None
            else None
        ),
        amends_filing_record_id=row.amends_filing_record_id,
        kind=row.kind,
        live_submission=row.live_submission,
    )


def _invalid_frame(
    completed: RegisteredOperationCompletion[ModeloFilingRecordListProjection],
) -> CliRefusedBoundaryError:
    return submitted_operation_error(
        completed.operation_id,
        RuntimeRefusalCode.INVALID_FRAME.value,
        terminal_condition=completed.terminal_condition,
        effect=completed.effect,
        refusal_code=completed.refusal_code,
    )


def read_modelo_filing_record_list(
    ctx: typer.Context,
    *,
    bucket_id: str | None,
    modelo: str | ModeloCode | None,
    include_superseded: bool,
) -> tuple[ModeloRecordPayload, ...]:
    """Return the complete list for the invocation's bound profile."""
    client = bound_profile_client(ctx)
    profile_id = str(client.profile_id)
    scoped_bucket_filter = bucket_id.strip() if bucket_id is not None and bucket_id.strip() else None
    if scoped_bucket_filter is not None and scoped_bucket_filter != profile_id:
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    modelo_filter = str(ModeloCode(str(modelo))) if modelo is not None else None
    request = ModeloFilingRecordListRequest(
        profile_id=client.profile_id,
        modelo=modelo_filter,
        include_superseded=include_superseded,
    )
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_FILING_RECORD_LIST_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(profile_id),
        result_type=ModeloFilingRecordListProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    projection = completed.projection
    try:
        valid_projection = isinstance(projection, ModeloFilingRecordListProjection) and (
            completed.terminal_condition is OperationTerminalCondition.SUCCEEDED
            and completed.refusal_code is None
            and completed.effect is OperationEffect.NONE
            and projection.result_version == 1
            and projection.profile_id == client.profile_id
            and projection.modelo == modelo_filter
            and projection.include_superseded is include_superseded
            and projection.record_count == len(projection.records)
            and all(row.bucket_id == profile_id for row in projection.records)
            and (modelo_filter is None or all(row.modelo == modelo_filter for row in projection.records))
            and (include_superseded or all(row.status is ModeloRecordStatus.VIGENTE for row in projection.records))
            and all(
                row.aeat_accepted == (row.confirmation is AeatConfirmationState.CONFIRMADA)
                for row in projection.records
            )
        )
    except Exception:
        valid_projection = False
    if not valid_projection:
        raise _invalid_frame(completed)
    try:
        return tuple(_payload_from_projection_row(row) for row in projection.records)
    except Exception:
        raise _invalid_frame(completed) from None


__all__ = ["read_modelo_filing_record_list"]
