"""Complete a settled-result request from the operation identity alone, and read why a stopped operation stopped."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import JsonValue

from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRequestV1,
)
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.operation_access import OperationObserve, OperationObserved
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from .operation_contract_cache import OperationContractCache
from .protocol_contract import parse_model

_RUNTIME_SUPPLIED = ("terminal_revision", "definition_contract_digest", "result_schema")


def resolve_result_request(
    client: FrontendClient, contracts: OperationContractCache, value: dict[str, Any], deadline: float
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
        OperationObserve(
            request_id=uuid4(), profile_id=client.profile_id, session_id=client.session_id, observation=request
        ),
        deadline=deadline,
    )
    if not isinstance(reply, OperationObserved):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    observation = reply.observation
    if not isinstance(observation, OperationObservationSuccessV1):
        raise FrontendRefusedError(observation.code.value)
    projection = observation.projection
    if projection.operation_id != request.operation_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
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
            raise FrontendRefusedError(OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE.value)
        supplied["result_schema"] = contract.result_schema.model_dump(mode="json")
    return parse_model(OperationResultProjectionRequestV1, supplied | value)


def stopped_operation_detail(
    client: FrontendClient,
    request: OperationResultProjectionRequestV1,
    document: dict[str, JsonValue],
    deadline: float,
) -> JsonValue:
    """Return the recorded detail of a refused or failed operation, or ``None`` when there is none to give.

    Such an operation has no result, so its result read says only that it was
    not successful. What it recorded about why (the registered code, the
    message key, the scrubbed context and any typed verdict) is read with the
    same settled-result read under the detail's own schema, which is how the
    command line reads it for the error it prints. An operation that recorded
    none, or a session that may not read it, leaves the code its observation
    already carries.
    """
    if (
        document.get("outcome") != "refused"
        or document.get("code") != OperationResultProjectionRefusalCode.OPERATION_NOT_SUCCESSFUL.value
    ):
        return None
    # Imported on use so that serving the other tools loads none of it.
    from cadrumo.application.operations.error_detail import operation_error_detail_schema

    schema = operation_error_detail_schema()
    if request.result_schema == schema:
        return None
    try:
        detail = client.read_result_document(request.model_copy(update={"result_schema": schema}), deadline=deadline)
    except (FrontendRefusedError, RefusalError):
        return None
    return detail.get("projection") if detail.get("outcome") == "success" else None
