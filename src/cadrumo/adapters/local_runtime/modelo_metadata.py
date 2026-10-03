"""Bounded native client for canonical modelo work-unit metadata operations."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from ...application.modelo.metadata_read_operation import (
    MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
    ModeloWorkMetadataProjection,
    ModeloWorkMetadataRequest,
)
from ...application.modelo.operation_definitions import (
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
)
from ...application.modelo.work_change_contracts import (
    ModeloWorkDiscardPublicResultV2,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from ...application.operations.frontend_requests import (
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationPublicDefinitionContractV1, OperationSchemaIdentityV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import bounded_deadline_after
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import (
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient
from .frontend_client_contracts import frontend_failure_code
from .operation_run_error_context import operation_run_error_context
from .operation_settlement import (
    PinnedConnection,
    read_settled_result_bytes,
    start_and_await_terminal,
    submit_operation,
)

type ModeloMetadataMutationRequest = ModeloWorkRenameRequest | ModeloWorkDiscardRequest
type ModeloMetadataMutationResult = ModeloWorkRenamePublicResultV2 | ModeloWorkDiscardPublicResultV2
type _MetadataResult = ModeloWorkMetadataProjection | ModeloMetadataMutationResult


@dataclass(frozen=True, slots=True)
class ModeloMetadataCompletion:
    """One settled operation and its exact persisted public result."""

    operation_id: OperationId
    projection: _MetadataResult
    effect: OperationEffect


class ModeloMetadataRunError(CadrumoError):
    """Retain a submitted ID and only settlement facts the native owner proved."""

    def __init__(
        self,
        *,
        operation_id: OperationId,
        code: str,
        terminal_condition: OperationTerminalCondition | None = None,
        effect: OperationEffect | None = None,
    ) -> None:
        """Expose a safe reason and durable recovery identity after submission."""
        self.operation_id = operation_id
        self.reason = code
        self.terminal_condition = terminal_condition
        self.effect = effect
        super().__init__(
            code,
            context=operation_run_error_context(
                code=code, operation_id=operation_id, terminal_condition=terminal_condition, effect=effect
            ),
        )


def _result(
    encoded: bytes, *, result_type: type[BaseModel], contract: OperationPublicDefinitionContractV1
) -> _MetadataResult:
    if result_type is ModeloWorkMetadataProjection:
        success = OperationResultProjectionSuccessV1[ModeloWorkMetadataProjection].model_validate_json(encoded)
    elif result_type is ModeloWorkRenamePublicResultV2:
        success = OperationResultProjectionSuccessV1[ModeloWorkRenamePublicResultV2].model_validate_json(encoded)
    elif result_type is ModeloWorkDiscardPublicResultV2:
        success = OperationResultProjectionSuccessV1[ModeloWorkDiscardPublicResultV2].model_validate_json(encoded)
    else:
        raise TypeError("unsupported modelo metadata result type")
    if (
        success.result_schema != contract.result_schema
        or success.definition_contract_digest != contract.definition_contract_digest
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return success.projection


def _run(
    client: RuntimeFrontendClient,
    request: BaseModel,
    *,
    definition_id: str,
    subject_ref: str,
    result_type: type[BaseModel],
    request_version: int,
    result_version: int,
    timeout: float,
) -> ModeloMetadataCompletion:
    deadline = bounded_deadline_after(timeout, subject="modelo metadata")
    contract = client.contract(definition_id, deadline=deadline)
    expected_request = OperationSchemaIdentityV1.from_model(
        schema_id=f"{definition_id}.request", schema_version=request_version, model_type=type(request)
    )
    expected_result = OperationSchemaIdentityV1.from_model(
        schema_id=f"{definition_id}.result", schema_version=result_version, model_type=result_type
    )
    _require_metadata_contract(client, contract, definition_id, expected_request, expected_result)
    pinned = PinnedConnection.of(client)
    submitted = submit_operation(
        client,
        pinned,
        definition_id=definition_id,
        subject_ref=subject_ref,
        payload_json=request.model_dump_json(),
        deadline=deadline,
    )
    operation_id = submitted.receipt.operation_id
    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    try:
        if submitted.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        terminal = start_and_await_terminal(
            client, pinned, operation_id, contract=contract, subject_ref=subject_ref, deadline=deadline
        )
        condition, effect = terminal.terminal_condition, terminal.effect
        if condition is not OperationTerminalCondition.SUCCEEDED:
            raise ModeloMetadataRunError(
                operation_id=operation_id,
                code=terminal.refusal_ref
                or terminal.failure_error_code
                or (condition.value if condition is not None else "unknown"),
                terminal_condition=condition,
                effect=effect,
            )
        result = _result(
            read_settled_result_bytes(client, operation_id, terminal, contract, deadline=deadline),
            result_type=result_type,
            contract=contract,
        )
        if client.session_id != pinned.session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return ModeloMetadataCompletion(operation_id=operation_id, projection=result, effect=effect)
    except ModeloMetadataRunError:
        raise
    except Exception as error:
        if isinstance(error, ValidationError):
            error = RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        raise ModeloMetadataRunError(
            operation_id=operation_id,
            code=frontend_failure_code(error),
            terminal_condition=condition,
            effect=effect,
        ) from error


def read_modelo_work_metadata(
    client: RuntimeFrontendClient, request: ModeloWorkMetadataRequest, *, timeout: float = 60
) -> ModeloMetadataCompletion:
    """Resolve one selector through the exact-profile worker and recorded read."""
    if request.profile_id != client.profile_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    completion = _run(
        client,
        request,
        definition_id=MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(client.profile_id)),
        result_type=ModeloWorkMetadataProjection,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )
    result = completion.projection
    if (
        not isinstance(result, ModeloWorkMetadataProjection)
        or result.profile_id != client.profile_id
        or result.unit.bucket_id != str(client.profile_id)
        or completion.effect is not OperationEffect.NONE
    ):
        raise ModeloMetadataRunError(
            operation_id=completion.operation_id,
            code=RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completion.effect,
        )
    return completion


def run_modelo_metadata_mutation(
    client: RuntimeFrontendClient, request: ModeloMetadataMutationRequest, *, timeout: float = 60
) -> ModeloMetadataCompletion:
    """Run one registered rename or discard and return its commit snapshot."""
    if type(request) is ModeloWorkRenameRequest:
        definition_id = MODELO_WORK_RENAME_OPERATION_DEFINITION_ID
        subject_ref = request.work_unit_id
        result_type: type[BaseModel] = ModeloWorkRenamePublicResultV2
        request_version = 2
    elif type(request) is ModeloWorkDiscardRequest:
        definition_id = MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID
        subject_ref = request.baseline.work_unit_id
        result_type = ModeloWorkDiscardPublicResultV2
        request_version = 1
    else:
        raise TypeError("unsupported modelo metadata request type")
    completion = _run(
        client,
        request,
        definition_id=definition_id,
        subject_ref=subject_ref,
        result_type=result_type,
        request_version=request_version,
        result_version=2,
        timeout=timeout,
    )
    result = completion.projection
    if (
        not isinstance(result, (ModeloWorkRenamePublicResultV2, ModeloWorkDiscardPublicResultV2))
        or type(result) is not result_type
        or result.work_unit_id != subject_ref
        or result.bucket_id != str(client.profile_id)
        or result.unit.work_unit_id != subject_ref
        or result.unit.bucket_id != str(client.profile_id)
        or completion.effect is not OperationEffect.UPDATED
    ):
        raise ModeloMetadataRunError(
            operation_id=completion.operation_id,
            code=RuntimeRefusalCode.INVALID_FRAME.value,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=completion.effect,
        )
    return completion


__all__ = [
    "ModeloMetadataCompletion",
    "ModeloMetadataMutationRequest",
    "ModeloMetadataRunError",
    "read_modelo_work_metadata",
    "run_modelo_metadata_mutation",
]


def _require_metadata_contract(
    client: RuntimeFrontendClient,
    contract: OperationPublicDefinitionContractV1,
    definition_id: str,
    expected_request: OperationSchemaIdentityV1,
    expected_result: OperationSchemaIdentityV1,
) -> None:
    """Require the exact metadata operation door before recording a submission."""
    if (
        contract.definition_id != definition_id
        or contract.request_schema != expected_request
        or contract.result_schema != expected_result
        or client.frontend not in contract.permitted_frontends
        or contract.ephemeral_secret_required
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
