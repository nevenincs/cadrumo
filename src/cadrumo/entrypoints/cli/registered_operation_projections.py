"""Decode and correlate registered CLI review-independent observation and result documents."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel, ValidationError

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from ...application.operations.error_detail import (
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from ...application.operations.frontend_projection import (
    OperationPublicProjectionV1,
)
from ...application.operations.frontend_requests import (
    OperationObservationRefusalV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationId
from ...application.operations.registry import (
    OperationPublicDefinitionContractV1,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.operation_access import (
    RuntimeOperationObserved,
    RuntimeOperationReply,
)
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationTerminalCondition
from .registered_operation_deadlines import MIN_SETTLED_OPERATION_READ_SECONDS


def decode_registered_observation(
    observed: RuntimeOperationReply,
    operation_id: OperationId,
    definition_id: str,
    subject_ref: str,
    contract: OperationPublicDefinitionContractV1,
) -> OperationPublicProjectionV1:
    """Validate the observed reply and every exact public operation coordinate."""
    if not isinstance(observed, RuntimeOperationObserved):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if isinstance(observed.observation, OperationObservationRefusalV1):
        raise RuntimeFrontendRefusedError(observed.observation.code.value)
    if not isinstance(observed.observation, OperationObservationSuccessV1):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    state = observed.observation.projection
    if (
        state.operation_id != operation_id
        or state.definition_id != definition_id
        or state.subject_ref != subject_ref
        or state.definition_contract != contract
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return state


def settled_registered_error_detail(
    client: RuntimeFrontendClient,
    *,
    operation_id: OperationId,
    terminal_revision: int,
    contract: OperationPublicDefinitionContractV1,
    condition: OperationTerminalCondition | None,
    deadline: float,
) -> OperationErrorDetailV1 | None:
    """Read a refused or failed operation's recorded detail, or ``None`` when it has none.

    The detail is presentation: an operation that recorded none, a session
    that may not read it, or a malformed document leaves the caller with the
    registered code the observation already carried.
    """
    if condition not in {OperationTerminalCondition.REFUSED, OperationTerminalCondition.FAILED}:
        return None
    schema = operation_error_detail_schema()
    try:
        document = client.read_result_document(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal_revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=schema,
            ),
            timeout=max(deadline - time.monotonic(), MIN_SETTLED_OPERATION_READ_SECONDS),
            deadline=deadline,
        )
        if document.get("outcome") == "refused":
            return None
        success = OperationResultProjectionSuccessV1[OperationErrorDetailV1].model_validate_json(
            canonical_json_bytes(document)
        )
    except (RuntimeRefusalError, RuntimeFrontendRefusedError, ValidationError, ValueError):
        return None
    if success.result_schema != schema or success.definition_contract_digest != contract.definition_contract_digest:
        return None
    return success.projection


def registered_result_projection[ResultT: BaseModel](
    document: Mapping[str, object],
    *,
    result_type: type[ResultT],
    contract: OperationPublicDefinitionContractV1,
) -> ResultT:
    """Decode the exact typed result and correlate its schema and defining contract."""
    encoded = canonical_json_bytes(document)
    if document.get("outcome") == "refused":
        refusal = OperationResultProjectionRefusalV1.model_validate_json(encoded)
        raise RuntimeFrontendRefusedError(refusal.code.value)
    # CAST-RATIONALE-CLI-REGISTERED-RESULT-GENERIC: Pydantic's runtime specialization binds the
    # success projection to this exact result_type; its __class_getitem__ typing stub is broad.
    success_type = cast(
        "type[OperationResultProjectionSuccessV1[ResultT]]",
        OperationResultProjectionSuccessV1.__class_getitem__(result_type),
    )
    success = success_type.model_validate_json(encoded)
    if (
        success.result_schema != contract.result_schema
        or success.definition_contract_digest != contract.definition_contract_digest
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    return success.projection
