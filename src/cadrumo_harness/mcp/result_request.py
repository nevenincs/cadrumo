"""Complete a settled-result request from the operation identity alone."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRequestV1,
)
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import RuntimeOperationObserve, RuntimeOperationObserved

from .operation_contract_cache import OperationContractCache
from .protocol_contract import parse_model

_RUNTIME_SUPPLIED = ("terminal_revision", "definition_contract_digest", "result_schema")


def resolve_result_request(
    client: RuntimeFrontendClient, contracts: OperationContractCache, value: dict[str, Any], deadline: float
) -> OperationResultProjectionRequestV1:
    """Parse a result request, reading any identifying value the caller left out.

    A caller that names the operation only gets the terminal revision from the
    operation's current observation, and the contract digest and result schema
    from its current contract. Values the caller supplies are never replaced;
    the runtime still checks each of them.
    """
    if "operation_id" not in value or all(key in value for key in _RUNTIME_SUPPLIED):
        return parse_model(OperationResultProjectionRequestV1, value)
    request = parse_model(
        OperationObservationRequestV1, {"operation_id": value["operation_id"], "after_cursor": 0, "page_limit": 1}
    )
    reply = client.operation(
        RuntimeOperationObserve(
            request_id=uuid4(), profile_id=client.profile_id, session_id=client.session_id, observation=request
        ),
        deadline=deadline,
    )
    if not isinstance(reply, RuntimeOperationObserved):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    observation = reply.observation
    if not isinstance(observation, OperationObservationSuccessV1):
        raise RuntimeFrontendRefusedError(observation.code.value)
    projection = observation.projection
    if projection.operation_id != request.operation_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    contract = contracts.description(
        client,
        projection.definition_id,
        deadline=deadline,
        digest=projection.definition_contract.definition_contract_digest,
    ).contract
    supplied: dict[str, Any] = {
        "terminal_revision": projection.revision,
        "definition_contract_digest": contract.definition_contract_digest,
    }
    if "result_schema" not in value:
        if contract.result_schema is None:
            raise RuntimeFrontendRefusedError(OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE.value)
        supplied["result_schema"] = contract.result_schema.model_dump(mode="json")
    return parse_model(OperationResultProjectionRequestV1, supplied | value)
