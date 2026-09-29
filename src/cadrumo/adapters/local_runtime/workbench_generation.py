"""Read the canonical workbench generation through one authenticated runtime."""

from __future__ import annotations

import math
import time
from functools import cache
from uuid import uuid4

from pydantic import ValidationError

from ...application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.registry import OperationPublicDefinitionContractV1
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from ...application.workbench_generation import WorkbenchGenerationV1
from ...application.workbench_generation_operation import (
    WORKBENCH_GENERATION_OPERATION_DEFINITION_ID,
    WorkbenchGenerationOperationRequest,
    build_workbench_generation_operation_definition,
    build_workbench_generation_operation_registration,
)
from ...application.workbench_generation_projection import (
    WorkbenchGenerationOperationProjection,
    restore_workbench_generation,
)
from ...core.external_constants import OutputLanguage
from ...core.hashing import canonical_json_bytes
from ...core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from .frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError


@cache
def _contract() -> OperationPublicDefinitionContractV1:
    definition = build_workbench_generation_operation_definition()
    return build_workbench_generation_operation_registration(definition).contract


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
    return remaining


def read_workbench_generation(
    client: RuntimeFrontendClient, *, output_language: OutputLanguage, timeout: float = 60
) -> WorkbenchGenerationV1:
    """Return one complete generation after exact contract and result validation.

    Every read is a separately recorded invocation. The caller owns the client;
    losing this observer never asserts cancellation of the canonical operation.
    """
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("workbench read timeout must be finite and at most 120 seconds")
    deadline = time.monotonic() + timeout
    profile_id, session_id = client.profile_id, client.session_id
    contract = client.contract(WORKBENCH_GENERATION_OPERATION_DEFINITION_ID, deadline=deadline)
    if contract != _contract() or contract.result_schema is None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    subject_ref = profile_operation_subject(str(profile_id))
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=session_id,
            definition_id=contract.definition_id,
            subject_ref=subject_ref,
            payload_json=WorkbenchGenerationOperationRequest(
                profile_id=profile_id, output_language=output_language
            ).model_dump_json(),
        ),
        deadline=deadline,
    )
    if not isinstance(submitted, RuntimeOperationSubmitted) or submitted.receipt.secret_requirement is not None:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    operation_id = submitted.receipt.operation_id
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
        reply = client.operation(
            RuntimeOperationObserve(
                request_id=uuid4(),
                profile_id=profile_id,
                session_id=session_id,
                observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=1),
            ),
            deadline=deadline,
        )
        if not isinstance(reply, RuntimeOperationObserved):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        observation = reply.observation
        if not isinstance(observation, OperationObservationSuccessV1):
            raise RuntimeFrontendRefusedError(observation.code.value)
        projection = observation.projection
        if (
            projection.operation_id != operation_id
            or projection.definition_id != contract.definition_id
            or projection.subject_ref != subject_ref
            or projection.definition_contract != contract
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            break
        time.sleep(min(0.02, _remaining(deadline)))
    if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise RuntimeFrontendRefusedError(
            projection.refusal_ref or projection.failure_error_code or "operation_unavailable"
        )
    if projection.effect is not OperationEffect.NONE:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    document = client.read_result_document(
        OperationResultProjectionRequestV1(
            operation_id=operation_id,
            terminal_revision=projection.revision,
            definition_contract_digest=contract.definition_contract_digest,
            result_schema=contract.result_schema,
        ),
        timeout=_remaining(deadline),
    )
    try:
        if document.get("outcome") == "refused":
            refusal = OperationResultProjectionRefusalV1.model_validate_json(canonical_json_bytes(document))
            raise RuntimeFrontendRefusedError(refusal.code.value)
        result = OperationResultProjectionSuccessV1[WorkbenchGenerationOperationProjection].model_validate_json(
            canonical_json_bytes(document)
        )
        if (
            result.result_schema != contract.result_schema
            or result.definition_contract_digest != contract.definition_contract_digest
            or result.projection.profile_id != profile_id
            or client.session_id != session_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        generation = restore_workbench_generation(result.projection)
    except (ValidationError, ValueError, TypeError):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME) from None
    _remaining(deadline)
    return generation
