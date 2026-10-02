"""CLI client for one exact-profile registered Modelo work amendment."""

from __future__ import annotations

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...application.modelo.amendment_context_operation import (
    MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,
    ModeloWorkAmendmentContextProjection,
    ModeloWorkAmendmentContextRequest,
)
from ...application.modelo.amendment_projection import ModeloWorkAmendPublicResultV2
from ...application.modelo.filing_selection_operation import (
    MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID,
    ModeloWorkFilingRecordProjection,
    ModeloWorkFilingRecordRequest,
)
from ...application.modelo.operation_definitions import (
    MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
    ModeloWorkAmendRequest,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .runtime_registered_operation import (
    RegisteredOperationCompletion,
    run_registered_operation,
    submitted_operation_error,
)


def read_modelo_work_filing_record(
    client: RuntimeFrontendClient, request: ModeloWorkFilingRecordRequest, *, timeout: float = 60
) -> RegisteredOperationCompletion[ModeloWorkFilingRecordProjection]:
    """Read the exact filing and its owning work unit under registered authority."""
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_FILING_RECORD_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloWorkFilingRecordProjection,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )
    result = completed.projection
    if (
        not isinstance(result, ModeloWorkFilingRecordProjection)
        or result.profile_id != client.profile_id
        or result.record.filing_record_id != request.filing_record_id
        or result.record.bucket_id != str(client.profile_id)
        or result.unit.bucket_id != str(client.profile_id)
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed


def read_modelo_work_amendment_context(
    client: RuntimeFrontendClient, request: ModeloWorkAmendmentContextRequest, *, timeout: float = 60
) -> RegisteredOperationCompletion[ModeloWorkAmendmentContextProjection]:
    """Read one filing and its calculation under a single pinned worker authority."""
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_AMENDMENT_CONTEXT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloWorkAmendmentContextProjection,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )
    result = completed.projection
    if (
        not isinstance(result, ModeloWorkAmendmentContextProjection)
        or result.profile_id != client.profile_id
        or result.record.filing_record_id != request.filing_record_id
        or result.record.bucket_id != str(client.profile_id)
        or result.unit.bucket_id != str(client.profile_id)
        or result.calculation.bucket_id != str(client.profile_id)
        or completed.effect is not OperationEffect.NONE
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed


def run_modelo_work_amendment(
    client: RuntimeFrontendClient,
    request: ModeloWorkAmendRequest,
    *,
    work_unit_id: str,
    timeout: float = 120,
) -> RegisteredOperationCompletion[ModeloWorkAmendPublicResultV2]:
    """Return the writer's complete local record from the registered operation."""
    completed = run_registered_operation(
        client,
        request,
        definition_id=MODELO_WORK_AMEND_OPERATION_DEFINITION_ID,
        subject_ref=work_unit_id,
        result_type=ModeloWorkAmendPublicResultV2,
        request_version=2,
        result_version=2,
        timeout=timeout,
    )
    result = completed.projection
    if (
        not isinstance(result, ModeloWorkAmendPublicResultV2)
        or result.record.bucket_id != str(client.profile_id)
        or result.record.work_unit_id != work_unit_id
        or result.source_filing_record_id != request.baseline.from_filing_record_id
        or result.amendment_kind is not request.amendment_kind
        or result.m303_rectificativa_motive is not request.m303_rectificativa_motive
        or completed.effect is not OperationEffect.UPDATED
    ):
        raise submitted_operation_error(
            completed.operation_id,
            RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completed.effect,
        )
    return completed


__all__ = ["read_modelo_work_amendment_context", "read_modelo_work_filing_record", "run_modelo_work_amendment"]
