"""A payload refused with a code alone is answered with the fields that explain it, where names do.

The runtime decodes a submitted payload with the operation's registered
request model and returns the model's faults with its refusal, which the
server passes on. A refusal can still arrive as a code alone, and the lease
here gives exactly that: it decodes each submission with the real registry's
own request model and answers ``invalid``, with no faults, when that model
raises. What is under test is the server's part for such a refusal, that it
names a missing or unknown field from the schema it described, repeats no
value, refuses nothing itself, and leaves a refusal about a value as it was
given. The faults the runtime itself returns are tested through a real one.
"""

from __future__ import annotations

import json
from typing import Any, NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.models import new_operation_id
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionDescriptionV1,
    OperationRegistry,
)
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    PROFILE_PATCH_OPERATION_DEFINITION_ID,
)
from cadrumo.core.hashing import sha256_hex
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_PRIVATE = "synthetic-private-value-2b7d"
_DIGEST = sha256_hex(b"synthetic profile content")
_MISSING = "this field is required"
_UNKNOWN = "the request has no such field"


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("no executor runs behind a lease that only decodes requests")


class _DecodingLease:
    """An admitted lease that refuses a submission exactly when the registered request model refuses it."""

    def __init__(self, profile_id: UUID, *, refusal: str = AutomationCustodyCode.INVALID.value) -> None:
        auth = build_auth_read_definition(_unused_ports)
        self.registry = OperationRegistry(
            definitions=(auth, *USER_PROFILE_OPERATION_DEFINITIONS),
            public_registrations=(
                build_auth_read_registration(auth),
                *build_user_profile_operation_registrations(USER_PROFILE_OPERATION_DEFINITIONS),
            ),
        )
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.accepted: list[RuntimeOperationSubmit] = []
        self._refusal = refusal

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        assert deadline > 0
        return self.registry.describe_public_definition(definition_id)

    def operation(self, request: object, *, deadline: float) -> object:
        assert deadline > 0
        boot, connection = uuid4(), uuid4()
        if isinstance(request, RuntimeOperationControl):
            return RuntimeOperationAcknowledged(
                request_id=request.request_id,
                runtime_boot_id=boot,
                connection_id=connection,
                operation_id=request.operation_id,
            )
        assert isinstance(request, RuntimeOperationSubmit), request
        try:
            self.registry.decode_request_payload(request.definition_id, request.payload_json)
        except (ValueError, TypeError):
            raise RuntimeFrontendRefusedError(self._refusal) from None
        self.accepted.append(request)
        return RuntimeOperationSubmitted(
            request_id=request.request_id,
            runtime_boot_id=boot,
            connection_id=connection,
            receipt=OperationSubmissionReceiptV1(operation_id=new_operation_id(), secret_requirement=None),
        )

    def close(self) -> None:
        return None


async def _execute(lease: _DecodingLease, definition_id: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    adapter = RuntimeMcpAdapter(profile_id=lease.profile_id, client=cast(RuntimeFrontendClient, lease))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            called = await sdk.call_tool("execute", {"definition_id": definition_id, "payload": payload})
    finally:
        await adapter.close()
    assert called.structured_content is not None
    return called.is_error, called.structured_content


def _patch(lease: _DecodingLease, **changed: object) -> dict[str, Any]:
    return {
        "profile_id": str(lease.profile_id),
        "expected_revision": 1,
        "expected_content_digest": _DIGEST,
        "values": [{"question_id": "tax-id", "value": _PRIVATE}],
        **changed,
    }


@pytest.mark.anyio
async def test_a_missing_required_field_is_named_and_the_payload_that_fits_is_submitted() -> None:
    lease = _DecodingLease(uuid4())

    refused_error, refused = await _execute(lease, AUTH_READ_OPERATION_DEFINITION_ID, {"kind": "status"})
    fits_error, fits = await _execute(
        lease, AUTH_READ_OPERATION_DEFINITION_ID, {"profile_id": str(lease.profile_id), "kind": "status"}
    )

    assert refused_error is True and (refused["outcome"], refused["code"]) == ("refused", "invalid")
    assert refused["faults"] == [{"location": ["profile_id"], "type": "missing", "message": _MISSING}]
    assert "request model" in refused["faults_cover"]
    assert fits_error is False and fits["outcome"] == "submitted" and "faults" not in fits
    assert [request.definition_id for request in lease.accepted] == [AUTH_READ_OPERATION_DEFINITION_ID]


@pytest.mark.anyio
async def test_every_missing_and_unknown_field_is_named_and_no_fault_repeats_a_value() -> None:
    lease = _DecodingLease(uuid4())
    payload = {"profile_id": str(lease.profile_id), "path": "identity.name", "valeu": _PRIVATE, "note": _PRIVATE}

    is_error, refused = await _execute(lease, PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID, payload)

    assert is_error is True and refused["code"] == "invalid"
    assert refused["faults"] == [
        {"location": ["expected_revision"], "type": "missing", "message": _MISSING},
        {"location": ["expected_content_digest"], "type": "missing", "message": _MISSING},
        {"location": ["value"], "type": "missing", "message": _MISSING},
        {"location": ["note"], "type": "extra_forbidden", "message": _UNKNOWN},
        {"location": ["valeu"], "type": "extra_forbidden", "message": _UNKNOWN},
    ]
    assert _PRIVATE not in json.dumps(refused) and lease.accepted == []


@pytest.mark.anyio
async def test_a_refusal_about_a_value_stays_as_the_runtime_gave_it() -> None:
    lease = _DecodingLease(uuid4())
    repeated = [{"question_id": "tax-id", "value": "a"}, {"question_id": "tax-id", "value": "b"}]

    # The request model refuses a patch that repeats a question, which no field name explains.
    rule_error, rule = await _execute(lease, PROFILE_PATCH_OPERATION_DEFINITION_ID, _patch(lease, values=repeated))
    bound_error, bound = await _execute(
        lease, PROFILE_PATCH_OPERATION_DEFINITION_ID, _patch(lease, expected_revision=0)
    )
    fits_error, fits = await _execute(lease, PROFILE_PATCH_OPERATION_DEFINITION_ID, _patch(lease))

    assert (rule_error, rule) == (True, {"outcome": "refused", "code": "invalid"})
    assert (bound_error, bound) == (True, {"outcome": "refused", "code": "invalid"})
    assert fits_error is False and fits["outcome"] == "submitted"
    assert _PRIVATE not in json.dumps([rule, bound, fits])


@pytest.mark.anyio
async def test_another_refusal_of_the_runtime_is_not_explained_as_a_fault_of_the_payload() -> None:
    lease = _DecodingLease(uuid4(), refusal="operation_denied")

    is_error, refused = await _execute(lease, AUTH_READ_OPERATION_DEFINITION_ID, {"kind": "status"})

    assert (is_error, refused) == (True, {"outcome": "refused", "code": "operation_denied"})


def test_the_execute_tool_says_what_faults_names() -> None:
    (described,) = [description for name, description, _schema in MCP_TOOL_CATALOGUE if name == "execute"]

    assert "faults names" in described and "never repeats a value" in described
