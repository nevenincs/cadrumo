"""Complete a settled-result request from the operation identity alone, and read why a stopped operation stopped."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from pydantic import JsonValue, ValidationError

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


def stopped_operation_code(document: dict[str, JsonValue]) -> str | None:
    """Return the closed refusal token of a refused result read, or ``None`` when the read was not refused.

    The token is the document's own registered result-projection refusal, for
    example ``operation_not_successful``, lifted beside it so a caller reads
    the refusal and its recovery from one level. A document whose code is not
    a registered token names none.
    """
    if document.get("outcome") != "refused":
        return None
    code = document.get("code")
    if not isinstance(code, str):
        return None
    try:
        return OperationResultProjectionRefusalCode(code).value
    except ValueError:
        return None


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


def stopped_operation_recovery_action(detail: JsonValue) -> str | None:
    """Return the operator action a stopped operation's precondition verdict names as its recovery, or ``None``.

    It is the same action the command line prints with the error, lifted out of
    the verdict's text so a caller reads one typed identifier, for example
    ``operator.provision.browser`` when a feature needs the browser set up.
    """
    from cadrumo.application.operations.error_detail import OperationErrorDetailV1

    if not isinstance(detail, dict):
        return None
    try:
        verdict = OperationErrorDetailV1.model_validate_json(json.dumps(detail)).precondition_verdict()
    except ValidationError:
        return None
    if verdict is None or verdict.action is None:
        return None
    return verdict.action.action_id


_VERDICT_FIELDS = frozenset({"failed_condition_id", "evidence", "conditionality"})
"""The members every published precondition verdict carries, by which the walk recognises one."""


def published_recovery_actions(document: dict[str, JsonValue]) -> tuple[str, ...]:
    """Return the recovery actions the verdicts of a succeeded result name, in document order, each once.

    A succeeded operation can still carry verdicts inside its result: an
    import that read some files and refused one for want of the local AI, or
    a batch paused for it. Each object of the published projection that reads
    as a precondition verdict counts; any other value names nothing.
    """
    from cadrumo.application.operator_actions.projection import PreconditionVerdictSnapshot

    if document.get("outcome") != "success":
        return ()
    found: list[str] = []

    def walk(value: JsonValue) -> None:
        if isinstance(value, dict):
            if set(value) >= _VERDICT_FIELDS:
                try:
                    verdict = PreconditionVerdictSnapshot.model_validate_json(json.dumps(value))
                except ValidationError:
                    verdict = None
                if verdict is not None and verdict.action_id is not None:
                    found.append(verdict.action_id)
                    return
            for member in value.values():
                walk(member)
        elif isinstance(value, list):
            for member in value:
                walk(member)

    walk(document.get("projection"))
    return tuple(dict.fromkeys(found))
