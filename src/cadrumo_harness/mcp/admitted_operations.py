"""Dispatch the authenticated operation projection of the MCP protocol."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationObservationRequestV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operator_output.runtime_remedies import runtime_unavailable_remedy
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationManage,
    RuntimeOperationObserve,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.projection_pages import ProjectionPageRequest
from cadrumo.core.time.clock import now

from .operation_contract_cache import OperationContractCache
from .operation_discovery import search_operations
from .protocol_contract import parse_model, public_value, refusal_code
from .result_request import resolve_result_request

_TIMEOUT = 30.0


class _AdmittedConnection(Protocol):
    profile_id: UUID
    client: RuntimeFrontendClient | None
    _startup_denial: str | None
    _contracts: OperationContractCache

    def _admitted(self) -> RuntimeFrontendClient: ...


@dataclass(frozen=True, slots=True)
class _Binding:
    """The connection-owned identity and memory every admitted tool call shares."""

    profile_id: UUID
    contracts: OperationContractCache


type _ToolHandler = Callable[[RuntimeFrontendClient, _Binding, dict[str, Any], float], dict[str, Any]]


def call_admitted_operation(connection: _AdmittedConnection, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Route one authenticated tool to its existing typed runtime operation."""
    if name == "status" and connection.client is None:
        return _unauthenticated_status(connection.profile_id, connection._startup_denial)
    client = connection._admitted()
    if name == "status":
        return {"outcome": "status", "status": public_value(client.status().status)}
    deadline = time.monotonic() + _TIMEOUT
    handler = _ADMITTED_TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError("unsupported tool")
    return handler(client, _Binding(connection.profile_id, connection._contracts), args, deadline)


def _unauthenticated_status(profile_id: UUID, denial: str | None) -> dict[str, Any]:
    reply: dict[str, Any] = {
        "outcome": "status",
        "profile_id": str(profile_id),
        "authenticated": False,
        "denial": denial or "authentication_required",
    }
    if remedy := runtime_unavailable_remedy(denial):
        reply["remedy"] = remedy
    return reply


def _search(client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float) -> dict[str, Any]:
    return search_operations(client, binding.contracts, binding.profile_id, args, deadline)


def _describe(
    client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float
) -> dict[str, Any]:
    description = binding.contracts.description(client, args["definition_id"], deadline=deadline, fresh=True)
    return {"outcome": "described", "description": public_value(description)}


def _execute(client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float) -> dict[str, Any]:
    definition_id = args["definition_id"]
    binding.contracts.description(client, definition_id, deadline=deadline)
    submission = _submission(client, args, definition_id)
    try:
        reply = client.operation(submission, deadline=deadline)
        if not isinstance(reply, RuntimeOperationSubmitted):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    except RuntimeRefusalError as error:
        return _unresolved_submission(error, submission.request_id, definition_id)
    except TimeoutError:
        return _unresolved_submission(RuntimeRefusalCode.DEADLINE_EXCEEDED.value, submission.request_id, definition_id)
    except OSError:
        return _unresolved_submission(RuntimeRefusalCode.CONNECTION_CLOSED.value, submission.request_id, definition_id)
    response: dict[str, Any] = {"outcome": "submitted", "receipt": public_value(reply.receipt)}
    if args.get("start", True) and reply.receipt.secret_requirement is None:
        response["start"] = _start_submitted_operation(client, reply.receipt.operation_id, deadline)
    return response


def _submission(client: RuntimeFrontendClient, args: dict[str, Any], definition_id: str) -> RuntimeOperationSubmit:
    payload_json = json.dumps(args["payload"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return RuntimeOperationSubmit(
        request_id=uuid4(),
        profile_id=client.profile_id,
        session_id=client.session_id,
        definition_id=definition_id,
        subject_ref=args["subject_ref"],
        payload_json=payload_json,
        idempotency_key=args.get("idempotency_key"),
    )


def _unresolved_submission(error: Exception | str, request_id: UUID, definition_id: str) -> dict[str, Any]:
    code = refusal_code(error) if isinstance(error, Exception) else error
    return {
        "outcome": "unresolved",
        "code": code,
        "request_id": str(request_id),
        "definition_id": definition_id,
    }


def _start_submitted_operation(client: RuntimeFrontendClient, operation_id: str, deadline: float) -> Any:
    try:
        acknowledgement = client.operation(
            RuntimeOperationControl(
                action="operation_start",
                request_id=uuid4(),
                profile_id=client.profile_id,
                session_id=client.session_id,
                operation_id=operation_id,
            ),
            deadline=deadline,
        )
        if not isinstance(acknowledgement, RuntimeOperationAcknowledged):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return public_value(acknowledgement)
    except Exception as error:
        # Submission is already durable; a lost start reply must retain its receipt.
        return {"outcome": "unresolved", "code": refusal_code(error)}


def _observe(
    client: RuntimeFrontendClient, _binding: _Binding, args: dict[str, Any], deadline: float
) -> dict[str, Any]:
    request = parse_model(OperationObservationRequestV1, args["observation"])
    reply = client.operation(
        RuntimeOperationObserve(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            observation=request,
        ),
        deadline=deadline,
    )
    return {"outcome": "reply", "reply": public_value(reply)}


def _result(client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float) -> dict[str, Any]:
    request = resolve_result_request(client, binding.contracts, args["result"], deadline)
    return {"outcome": "reply", "document": client.read_result_document(request, deadline=deadline)}


def _result_page(
    client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float
) -> dict[str, Any]:
    request = resolve_result_request(client, binding.contracts, args["result"], deadline)
    page = parse_model(ProjectionPageRequest, args["page"])
    released = client.read_result_page(request, page, deadline=deadline)
    return {"outcome": "reply", "page": public_value(released)}


def _review(client: RuntimeFrontendClient, _binding: _Binding, args: dict[str, Any], deadline: float) -> dict[str, Any]:
    request = parse_model(OperationReviewProjectionRequestV1, args["review"])
    reply = client.operation(
        RuntimeOperationReview(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            review=request,
        ),
        deadline=deadline,
    )
    return {"outcome": "reply", "reply": public_value(reply)}


def _respond(
    client: RuntimeFrontendClient, _binding: _Binding, args: dict[str, Any], deadline: float
) -> dict[str, Any]:
    action = args["action"]
    if "reason_code" in args and action != "reject":
        raise ValueError("only rejection accepts a reason code")
    fields = _response_fields(client, args)
    request = _response_request(action, fields, args)
    reply = client.operation(
        RuntimeOperationManage(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            management=request,
        ),
        deadline=deadline,
    )
    return {"outcome": "reply", "reply": public_value(reply)}


def _response_fields(client: RuntimeFrontendClient, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation_id": args["operation_id"],
        "interaction_id": args["interaction_id"],
        "revision": args["revision"],
        "actor_ref": f"session:{client.session_id}",
    }


def _response_request(action: str, fields: dict[str, Any], args: dict[str, Any]) -> Any:
    if action == "inspect":
        return parse_model(OperationResponseControlRequestV1, fields)
    if action == "apply":
        return parse_model(OperationResponseApplyRequestV1, fields | {"responded_at": now().isoformat()})
    return parse_model(
        OperationResponseRejectRequestV1,
        fields | {"responded_at": now().isoformat(), "reason_code": args.get("reason_code")},
    )


def _control(
    client: RuntimeFrontendClient, _binding: _Binding, args: dict[str, Any], deadline: float
) -> dict[str, Any]:
    action = args["action"]
    operation_id = args["operation_id"]
    if action in {"start", "resume"}:
        reply = _control_start_or_resume(client, action, operation_id, args, deadline)
    else:
        reply = _control_cancel_or_detach(client, action, operation_id, args, deadline)
    return {"outcome": "reply", "reply": public_value(reply)}


def _control_start_or_resume(
    client: RuntimeFrontendClient, action: str, operation_id: str, args: dict[str, Any], deadline: float
) -> Any:
    if "expected_revision" in args:
        raise ValueError("revision is not used by start or resume")
    return client.operation(
        RuntimeOperationControl(
            action="operation_start" if action == "start" else "operation_resume",
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            operation_id=operation_id,
        ),
        deadline=deadline,
    )


def _control_cancel_or_detach(
    client: RuntimeFrontendClient, action: str, operation_id: str, args: dict[str, Any], deadline: float
) -> Any:
    if "expected_revision" not in args:
        raise ValueError("cancel and detach require a revision")
    kind = OperationCancellationRequestV1 if action == "cancel" else OperationDetachRequestV1
    management = parse_model(kind, {"operation_id": operation_id, "expected_revision": args["expected_revision"]})
    return client.operation(
        RuntimeOperationManage(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            management=management,
        ),
        deadline=deadline,
    )


_ADMITTED_TOOL_HANDLERS: dict[str, _ToolHandler] = {
    "search": _search,
    "describe": _describe,
    "execute": _execute,
    "observe": _observe,
    "result": _result,
    "result_page": _result_page,
    "review": _review,
    "respond": _respond,
    "control": _control,
}
