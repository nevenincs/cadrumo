"""Bounded native client for canonical modelo work-unit metadata operations."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import uuid4

from pydantic import BaseModel, ValidationError

from ...application.modelo.metadata_read_operation import (
    MODELO_WORK_METADATA_OPERATION_DEFINITION_ID,
    ModeloWorkMetadataProjection,
    ModeloWorkMetadataRequest,
)
from ...application.modelo.operation_definitions import (
    MODELO_WORK_DISCARD_OPERATION_DEFINITION_ID,
    MODELO_WORK_RENAME_OPERATION_DEFINITION_ID,
    ModeloWorkDiscardPublicResultV2,
    ModeloWorkDiscardRequest,
    ModeloWorkRenamePublicResultV2,
    ModeloWorkRenameRequest,
)
from ...application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import OperationPublicDefinitionContractV1, OperationSchemaIdentityV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...core.errors.hierarchy import CadrumoError
from ...core.hashing import canonical_json_bytes
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError

type ModeloMetadataMutationRequest = ModeloWorkRenameRequest | ModeloWorkDiscardRequest
type ModeloMetadataMutationResult = ModeloWorkRenamePublicResultV2 | ModeloWorkDiscardPublicResultV2
type _MetadataResult = ModeloWorkMetadataProjection | ModeloMetadataMutationResult

_MAX_TIMEOUT_SECONDS = 120.0


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
        context = {
            "reason": code,
            "operation_id": str(operation_id),
            "effect": effect.value if effect is not None else "unknown",
        }
        if terminal_condition is not None:
            context["terminal_condition"] = terminal_condition.value
        super().__init__(code, context=context)


def _deadline(timeout: float) -> float:
    if not math.isfinite(timeout) or not 0 < timeout <= _MAX_TIMEOUT_SECONDS:
        raise ValueError("modelo metadata timeout must be finite and at most 120 seconds")
    return time.monotonic() + timeout


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def _failure_code(error: Exception) -> str:
    if isinstance(error, RuntimeFrontendRefusedError):
        return error.reason
    if isinstance(error, RuntimeRefusalError):
        return error.reason.value
    return RuntimeRefusalCode.UNAVAILABLE.value


def _result(
    document: Mapping[str, object], *, result_type: type[BaseModel], contract: OperationPublicDefinitionContractV1
) -> _MetadataResult:
    encoded = canonical_json_bytes(document)
    if document.get("outcome") == "refused":
        refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
        raise RuntimeFrontendRefusedError(refusal.code.value)
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
    deadline = _deadline(timeout)
    contract = client.contract(definition_id, deadline=deadline)
    expected_request = OperationSchemaIdentityV1.from_model(
        schema_id=f"{definition_id}.request", schema_version=request_version, model_type=type(request)
    )
    expected_result = OperationSchemaIdentityV1.from_model(
        schema_id=f"{definition_id}.result", schema_version=result_version, model_type=result_type
    )
    if (
        contract.definition_id != definition_id
        or contract.request_schema != expected_request
        or contract.result_schema != expected_result
        or client.frontend not in contract.permitted_frontends
        or contract.ephemeral_secret_required
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    profile_id, session_id = client.profile_id, client.session_id
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload_json=request.model_dump_json(),
        ),
        deadline=deadline,
    )
    if not isinstance(submitted, RuntimeOperationSubmitted):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id
    condition: OperationTerminalCondition | None = None
    effect: OperationEffect | None = None
    try:
        if submitted.receipt.secret_requirement is not None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        started = client.operation(
            RuntimeOperationControl(
                action="operation_start",
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                operation_id=operation_id,
            ),
            deadline=deadline,
        )
        if not isinstance(started, RuntimeOperationAcknowledged) or started.operation_id != operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        while True:
            _remaining(deadline)
            if client.session_id != session_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            observed = client.operation(
                RuntimeOperationObserve(
                    request_id=uuid4(),
                    profile_id=profile_id,
                    session_id=session_id,
                    observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
                ),
                deadline=deadline,
            )
            if not isinstance(observed, RuntimeOperationObserved):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if isinstance(observed.observation, OperationObservationRefusalV1):
                raise RuntimeFrontendRefusedError(observed.observation.code.value)
            if not isinstance(observed.observation, OperationObservationSuccessV1):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            observed_state = observed.observation.projection
            if (
                observed_state.operation_id != operation_id
                or observed_state.definition_id != definition_id
                or observed_state.subject_ref != subject_ref
                or observed_state.definition_contract != contract
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if observed_state.lifecycle is OperationLifecycle.TERMINAL:
                condition, effect = observed_state.terminal_condition, observed_state.effect
                break
            time.sleep(min(0.02, _remaining(deadline)))
        if condition is not OperationTerminalCondition.SUCCEEDED:
            raise ModeloMetadataRunError(
                operation_id=operation_id,
                code=observed_state.refusal_ref
                or observed_state.failure_error_code
                or (condition.value if condition is not None else "unknown"),
                terminal_condition=condition,
                effect=effect,
            )
        document = client.read_result_document(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=observed_state.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=expected_result,
            ),
            timeout=_remaining(deadline),
        )
        result = _result(document, result_type=result_type, contract=contract)
        if client.session_id != session_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return ModeloMetadataCompletion(operation_id=operation_id, projection=result, effect=effect)
    except ModeloMetadataRunError:
        raise
    except Exception as error:
        if isinstance(error, ValidationError):
            error = RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        raise ModeloMetadataRunError(
            operation_id=operation_id,
            code=_failure_code(error),
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
