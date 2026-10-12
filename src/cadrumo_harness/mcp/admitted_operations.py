"""Dispatch the authenticated operation projection of the MCP protocol."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final, Protocol
from uuid import UUID, uuid4

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationObservationRequestV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationReviewProjectionRequestV1,
)
from cadrumo.application.operations.mcp_surfaces import McpSurface
from cadrumo.application.operations.registry import (
    OperationPublicDefinitionContractV1,
    OperationPublicDefinitionDescriptionV1,
)
from cadrumo.application.operations.subject_reference import (
    OperationSubjectKind,
    OperationSubjectReferenceV1,
    expected_operation_subject,
)
from cadrumo.application.operator_output.runtime_remedies import runtime_unavailable_remedy
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.deadline_budget import remaining_budget
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationFinancialInput,
    RuntimeOperationManage,
    RuntimeOperationObserve,
    RuntimeOperationReview,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.projection_pages import ProjectionPageRequest
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.time.clock import now

from .operation_contract_cache import OperationContractCache
from .operation_discovery import search_operations
from .payload_vocabulary import PAYLOAD_VOCABULARY_MEMBER, payload_vocabulary
from .protocol_contract import BY_REFERENCE_SUFFIX, parse_model, public_value, refusal_code
from .result_request import resolve_result_request, stopped_operation_detail
from .runtime_admission import McpAdmission, status_on_surface
from .session_acts import NO_SESSION, act_on_sessions

_TIMEOUT = 30.0
_SECRET_DELIVERY_TIMEOUT = 20.0


class _AdmittedConnection(Protocol):
    profile_id: UUID | None
    client: RuntimeFrontendClient | None
    admission: McpAdmission | None
    surface: McpSurface
    _admission_denial: str | None
    _contracts: OperationContractCache

    def _admitted(self) -> RuntimeFrontendClient: ...

    def held_secret(self, reference: UUID) -> bytearray: ...

    def check_held_secret(self, reference: UUID) -> None: ...


@dataclass(frozen=True, slots=True)
class _Binding:
    """The connection-owned identity and memory every admitted tool call shares."""

    profile_id: UUID
    contracts: OperationContractCache
    surface: McpSurface
    admission: McpAdmission
    held_secret: Callable[[UUID], bytearray]
    check_held_secret: Callable[[UUID], None]


type _ToolHandler = Callable[[RuntimeFrontendClient, _Binding, dict[str, Any], float], dict[str, Any]]


def call_admitted_operation(connection: _AdmittedConnection, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Route one authenticated tool to its existing typed runtime operation."""
    if name == "status" and connection.client is None:
        return _unauthenticated_status(connection)
    client = connection._admitted()
    profile_id, admission = connection.profile_id, connection.admission
    if profile_id is None or admission is None:
        # A lease is held only for a bound profile and a known admission.
        raise RuntimeFrontendRefusedError(AccessDenialCode.PROFILE_MISMATCH.value)
    if name == "status":
        return _admitted_status(client, admission, connection.surface)
    deadline = time.monotonic() + _TIMEOUT
    handler = _ADMITTED_TOOL_HANDLERS.get(name)
    if handler is None:
        raise ValueError("unsupported tool")
    binding = _Binding(
        profile_id,
        connection._contracts,
        connection.surface,
        admission,
        connection.held_secret,
        connection.check_held_secret,
    )
    return handler(client, binding, args, deadline)


def _unauthenticated_status(connection: _AdmittedConnection) -> dict[str, Any]:
    """Say that no session is held, for which profile, and what the last admission was refused for."""
    denial = connection._admission_denial
    reply: dict[str, Any] = {
        "outcome": "status",
        "profile_id": None if connection.profile_id is None else str(connection.profile_id),
        "authenticated": False,
        "session": NO_SESSION,
        "surface": connection.surface.name.value,
        "denial": denial or "authentication_required",
    }
    if remedy := runtime_unavailable_remedy(denial):
        reply["remedy"] = remedy
    return reply


def _admitted_status(client: RuntimeFrontendClient, admission: McpAdmission, surface: McpSurface) -> dict[str, Any]:
    """Say how the held session was admitted, and its scope as the surface leaves it."""
    status = status_on_surface(client.status().status, surface)
    return {
        "outcome": "status",
        # A lease the runtime now denies is no session, whatever admitted it.
        "session": admission.value if status.denial is None else NO_SESSION,
        "surface": surface.name.value,
        "status": public_value(status),
    }


def _search(client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float) -> dict[str, Any]:
    return search_operations(
        client, binding.contracts, binding.profile_id, args, deadline, binding.surface, admission=binding.admission
    )


def _describe(
    client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float
) -> dict[str, Any]:
    definition_id = args["definition_id"]
    if not binding.surface.admits(definition_id):
        # The runtime refuses the operation itself; this only answers as it would.
        raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
    return described_reply(binding.contracts.description(client, definition_id, deadline=deadline, fresh=True))


def described_reply(description: OperationPublicDefinitionDescriptionV1) -> dict[str, Any]:
    """Build the ``describe`` reply for one public description, wherever it was read from.

    The typed operator input of a financial operand and the vocabulary a
    payload names come from the published authority and the installed
    package, so they are the same with a session and without one.
    """
    reply: dict[str, Any] = {"outcome": "described", "description": public_value(description)}
    if description.contract.transient_financial_operand is not None:
        reply["operator_input_json_schema"] = _operator_input_json_schema()
    vocabulary = payload_vocabulary(description.contract.definition_id)
    if vocabulary is not None:
        reply[PAYLOAD_VOCABULARY_MEMBER] = vocabulary
    return reply


def _operator_input_json_schema() -> dict[str, object]:
    """Return the schema of the typed operator input the runtime decodes for a financial operand.

    The registered request of such an operation carries no amount: the
    runtime builds it from this input, which every frontend submits in its
    place. Imported on use so that serving the other tools loads none of it.
    """
    from cadrumo.application.modelo.edit_operator_input import ModeloEditOperatorInputV2
    from cadrumo.application.operations.registry_schema_validation import strict_model_json_schema

    return strict_model_json_schema(ModeloEditOperatorInputV2)


def _execute(client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], deadline: float) -> dict[str, Any]:
    definition_id = args["definition_id"]
    # Taken out of the call before anything can fail, so no later step holds or repeats the text.
    secret_text = args.pop("secret", None)
    secret_reference = args.pop(f"secret{BY_REFERENCE_SUFFIX}", None)
    description = binding.contracts.description(client, definition_id, deadline=deadline)
    contract = description.contract
    secret: _CallSecret | None = None
    try:
        try:
            secret = _typed_secret(contract, secret_text, secret_reference, binding)
            submission = _submission(client, contract, args)
        except _ContractRefusedError as refused:
            # Nothing was submitted, and the wording quotes only the public contract.
            return {"outcome": "refused", "code": "invalid_request", "message": str(refused)}
        try:
            reply = client.operation(submission, deadline=deadline)
            if not isinstance(reply, RuntimeOperationSubmitted):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        except RuntimeFrontendRefusedError as refused:
            if refused.request_faults:
                # The request model's own reasons, as the runtime returned them without the values.
                return {
                    "outcome": "refused",
                    "code": refusal_code(refused),
                    "faults": [public_value(fault) for fault in refused.request_faults],
                }
            faults = _named_field_faults(refused, description, args["payload"])
            if not faults:
                raise
            return {
                "outcome": "refused",
                "code": refusal_code(refused),
                "faults": faults,
                "faults_cover": _FAULTS_COVER,
            }
        except RuntimeRefusalError as error:
            return _unresolved_submission(error, submission.request_id, definition_id)
        except TimeoutError:
            return _unresolved_submission(
                RuntimeRefusalCode.DEADLINE_EXCEEDED.value, submission.request_id, definition_id
            )
        except OSError:
            return _unresolved_submission(
                RuntimeRefusalCode.CONNECTION_CLOSED.value, submission.request_id, definition_id
            )
        response: dict[str, Any] = {"outcome": "submitted", "receipt": public_value(reply.receipt)}
        ready = True
        if secret is not None or reply.receipt.secret_requirement is not None:
            delivery = _deliver_secret(client, reply, submission, secret, deadline)
            response["secret_delivery"] = delivery
            ready = delivery["outcome"] == "delivered"
        if args.get("start", True) and ready:
            response["start"] = _start_submitted_operation(client, reply.receipt.operation_id, deadline)
        return response
    finally:
        if secret is not None:
            secret.wipe()


_FAULTS_COVER: Final = (
    "the payload's own fields by name, against the request schema describe returns; the request model can "
    "refuse a payload for a rule about a value, which this list does not show"
)


def _named_field_faults(
    refused: RuntimeFrontendRefusedError, description: OperationPublicDefinitionDescriptionV1, payload: object
) -> list[dict[str, Any]]:
    """Name the fields that explain why the runtime's request model refused a payload, where names do.

    A runtime that returns its model's faults is answered with those. This
    explains a refusal that came with a code and nothing else. Which fields
    the model requires and which it knows are in the schema already described,
    so a missing or unknown field is named from there. Only a refusal the
    runtime gave is explained: nothing is refused here, and no fault carries a
    value.
    """
    schema = description.request_json_schema
    properties = schema.get("properties")
    if (
        refused.reason != AutomationCustodyCode.INVALID.value
        or description.contract.transient_financial_operand is not None
        or not isinstance(payload, dict)
        or not isinstance(properties, dict)
    ):
        return []
    required = schema.get("required")
    missing = [name for name in required if name not in payload] if isinstance(required, list) else []
    closed = schema.get("additionalProperties") is False
    unknown = sorted(str(name) for name in payload if name not in properties) if closed else []
    return [
        *({"location": [name], "type": "missing", "message": "this field is required"} for name in missing),
        *(
            {"location": [name], "type": "extra_forbidden", "message": "the request has no such field"}
            for name in unknown
        ),
    ]


class _ContractRefusedError(ValueError):
    """The call does not fit what its operation's contract declares."""


class _CallSecret:
    """The typed secret of one call: its text, or a reference that is read only when the secret is sent.

    Reading a secret held for one use spends it, so a reference is read by
    ``take`` alone, which the delivery calls once everything else has passed.
    """

    def __init__(self, *, text: str | None, reference: UUID | None, read: Callable[[UUID], bytearray]) -> None:
        self._buffer = None if text is None else bytearray(text, "utf-8")
        self._reference = reference
        self._read = read

    def take(self) -> bytearray:
        """Return the secret's buffer, reading it from the store if it was given by reference."""
        if self._buffer is None:
            if self._reference is None:
                raise ValueError("no secret was given")
            self._buffer = self._read(self._reference)
        return self._buffer

    def wipe(self) -> None:
        """Overwrite the buffer, if one was ever filled."""
        if self._buffer is not None:
            self._buffer[:] = bytes(len(self._buffer))


def _typed_secret(
    contract: OperationPublicDefinitionContractV1, text: object, reference: object, binding: _Binding
) -> _CallSecret | None:
    """Hold the call to the typed secret its contract declares, and return the one that belongs.

    Given as text, the bytes are its UTF-8 encoding, which is what the
    command line sends for the same operation. Given by reference, they are
    the bytes held under it in the credential store. The store is asked here
    only whether something is held, once the contract is known to take it; the
    secret is read, and spent if it was held for one use, when it is sent.
    """
    if not contract.ephemeral_secret_required:
        if text is not None or reference is not None:
            raise _ContractRefusedError("secret is not accepted: this operation's contract declares no typed secret")
        return None
    if reference is not None:
        if text is not None:
            raise _ContractRefusedError("secret is given as text or by reference, not both")
        held = UUID(str(reference))
        binding.check_held_secret(held)
        return _CallSecret(text=None, reference=held, read=binding.held_secret)
    if not isinstance(text, str) or not text:
        raise _ContractRefusedError("secret is required: this operation's contract says ephemeral_secret_required")
    return _CallSecret(text=text, reference=None, read=binding.held_secret)


def _deliver_secret(
    client: RuntimeFrontendClient,
    submitted: RuntimeOperationSubmitted,
    submission: RuntimeOperationSubmit | RuntimeOperationFinancialInput,
    secret: _CallSecret | None,
    deadline: float,
) -> dict[str, Any]:
    """Hand the typed secret to the exact wait its submission opened, on the protected secret frame.

    The submission is already durable, so every outcome keeps its receipt: a
    refusal says the runtime took no secret, and anything else that goes
    wrong leaves unknown whether it did. A secret given by reference is read
    here, after the wait it is for has been matched and immediately before it
    is sent, so a call that never gets this far spends none. Once read, a
    secret held for one use is spent whether or not the send succeeds.
    """
    requirement = submitted.receipt.secret_requirement
    if (
        requirement is None
        or secret is None
        or requirement.identity.operation_id != submitted.receipt.operation_id
        or requirement.identity.definition_id != submission.definition_id
        or requirement.identity.subject_ref != submission.subject_ref
    ):
        # The runtime's wait and the contract this call was held to disagree, so nothing is sent.
        return {"outcome": "refused", "code": RuntimeRefusalCode.INVALID_FRAME.value}
    try:
        buffer = secret.take()
    except (ValueError, AutomationCustodyError) as unavailable:
        # Another call took it between the check and now, or the store cannot be read: nothing was sent.
        return {"outcome": "refused", "code": refusal_code(unavailable)}
    try:
        acknowledged = client.submit_secret(
            requirement, buffer, timeout=min(_SECRET_DELIVERY_TIMEOUT, remaining_budget(deadline))
        )
        if acknowledged.operation_id != submitted.receipt.operation_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    except RuntimeFrontendRefusedError as error:
        return {"outcome": "refused", "code": refusal_code(error)}
    except Exception as error:
        return {"outcome": "unresolved", "code": refusal_code(error)}
    return {"outcome": "delivered"}


class _SubjectRefusedError(_ContractRefusedError):
    """The call cannot be given the subject its operation's contract declares."""


def _subject_form(reference: OperationSubjectReferenceV1) -> str:
    """Say in words where the declared subject comes from."""
    field = ".".join(reference.payload_path)
    if reference.kind is OperationSubjectKind.PROFILE:
        return "the admitted profile"
    if reference.kind is OperationSubjectKind.FIXED:
        return f"the fixed subject {reference.literal}"
    if reference.kind is OperationSubjectKind.PAYLOAD_FIELD:
        return f"payload field {field}"
    if reference.kind is OperationSubjectKind.PAYLOAD_FIELD_OR_PROFILE:
        return f"payload field {field} when it is set, otherwise the admitted profile"
    return f"the work unit that owns the record named by payload field {field}"


def _subject(reference: OperationSubjectReferenceV1, profile_id: UUID, args: dict[str, Any]) -> str:
    """Derive the subject the contract declares, holding a supplied one to it.

    A stored work unit is the one subject the payload cannot yield, so there
    the caller's own value is passed on for the runtime to check.
    """
    supplied = args.get("subject_ref")
    try:
        derived = expected_operation_subject(reference, profile_id=profile_id, payload=args["payload"])
    except ValueError:
        raise _SubjectRefusedError(
            f"payload does not carry {'.'.join(reference.payload_path)}, which is this operation's subject"
        ) from None
    if derived is None:
        if not isinstance(supplied, str):
            raise _SubjectRefusedError(f"subject_ref is required: it is {_subject_form(reference)}")
        return supplied
    if supplied is not None and supplied != derived:
        raise _SubjectRefusedError(
            f"subject_ref does not match this operation's subject, which is {_subject_form(reference)}; "
            "leave subject_ref out and it is derived"
        )
    return derived


def _submission(
    client: RuntimeFrontendClient, contract: OperationPublicDefinitionContractV1, args: dict[str, Any]
) -> RuntimeOperationSubmit | RuntimeOperationFinancialInput:
    """Build the submission the contract calls for: the registered request, or the typed operator input."""
    payload_json = json.dumps(args["payload"], ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if contract.transient_financial_operand is None:
        return RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            definition_id=contract.definition_id,
            subject_ref=_subject(contract.subject_reference, client.profile_id, args),
            payload_json=payload_json,
            idempotency_key=args.get("idempotency_key"),
        )
    # The payload is the operator input and not the registered request, so the
    # subject cannot be read from it; the runtime holds the supplied one to the input.
    subject_ref = args.get("subject_ref")
    if not isinstance(subject_ref, str):
        raise _SubjectRefusedError(
            f"subject_ref is required with typed operator input: it is {_subject_form(contract.subject_reference)} "
            "of the registered request"
        )
    if "idempotency_key" in args:
        raise _ContractRefusedError("idempotency_key is not accepted with typed operator input")
    return RuntimeOperationFinancialInput(
        request_id=uuid4(),
        profile_id=client.profile_id,
        session_id=client.session_id,
        definition_id=contract.definition_id,
        subject_ref=subject_ref,
        payload_json=payload_json,
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
    document = client.read_result_document(request, deadline=deadline)
    reply: dict[str, Any] = {"outcome": "reply", "document": document}
    detail = stopped_operation_detail(client, request, document, deadline)
    if detail is not None:
        reply["error_detail"] = detail
    return reply


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


def _session(
    client: RuntimeFrontendClient, binding: _Binding, args: dict[str, Any], _deadline: float
) -> dict[str, Any]:
    return act_on_sessions(client, binding.admission, args)


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
    "session": _session,
}
