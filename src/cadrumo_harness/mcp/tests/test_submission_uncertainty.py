"""Lost MCP submit replies cannot be presented as known prewrite refusals."""

from __future__ import annotations

from typing import Literal, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import RuntimeOperationSubmit, RuntimeOperationSubmitted
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.core.operations import profile_operation_subject
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


class _SubmitClient:
    def __init__(
        self,
        profile_id: UUID,
        *,
        fail_description: bool = False,
        submit_failure: Literal["runtime", "timeout", "os", "access", "wire_runtime", "wire_access"] = "runtime",
    ) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.fail_description = fail_description
        self.submit_failure = submit_failure
        self.submissions: list[RuntimeOperationSubmit] = []
        self.closed = False

    def describe(self, _definition_id: str, *, deadline: float) -> object:
        assert deadline > 0
        if self.fail_description:
            raise RuntimeFrontendRefusedError("operation_denied")
        return object()

    def operation(self, request: RuntimeOperationSubmit, *, deadline: float) -> object:
        assert deadline > 0
        self.submissions.append(request)
        if self.submit_failure == "timeout":
            raise TimeoutError("synthetic transport timeout")
        if self.submit_failure == "os":
            raise OSError("synthetic transport close failure")
        if self.submit_failure == "access":
            raise RuntimeFrontendRefusedError("operation_denied")
        if self.submit_failure in {"wire_runtime", "wire_access"}:
            RuntimeFrontendClient._reply(
                RuntimeAccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=uuid4(),
                    connection_id=uuid4(),
                    code=RuntimeRefusalCode.DEADLINE_EXCEEDED
                    if self.submit_failure == "wire_runtime"
                    else AccessDenialCode.PERIOD_DENIED,
                ),
                RuntimeOperationSubmitted,
            )
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failure", "code"),
    (
        ("runtime", RuntimeRefusalCode.DEADLINE_EXCEEDED.value),
        ("wire_runtime", RuntimeRefusalCode.DEADLINE_EXCEEDED.value),
        ("timeout", RuntimeRefusalCode.DEADLINE_EXCEEDED.value),
        ("os", RuntimeRefusalCode.CONNECTION_CLOSED.value),
    ),
)
async def test_lost_submit_reply_is_unresolved_with_only_safe_request_correlation(
    failure: Literal["runtime", "wire_runtime", "timeout", "os"], code: str
) -> None:
    profile_id = uuid4()
    client = _SubmitClient(profile_id, submit_failure=failure)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            submitted = await sdk.call_tool(
                "execute",
                {
                    "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                    "subject_ref": profile_operation_subject(str(profile_id)),
                    "payload": {"kind": "status"},
                },
            )
            assert submitted.is_error is True
            result = submitted.structured_content
            assert result is not None
            assert result["outcome"] == "unresolved"
            assert result["code"] == code
            assert result["definition_id"] == AUTH_READ_OPERATION_DEFINITION_ID
            assert "operation_id" not in result and "receipt" not in result
            assert len(client.submissions) == 1
            assert UUID(str(result["request_id"])) == client.submissions[0].request_id
    finally:
        await adapter.close()
    assert client.closed


@pytest.mark.anyio
async def test_known_pre_submit_description_denial_stays_refused_without_dispatch() -> None:
    profile_id = uuid4()
    client = _SubmitClient(profile_id, fail_description=True)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call(
            "execute",
            {
                "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                "subject_ref": profile_operation_subject(str(profile_id)),
                "payload": {"kind": "status"},
            },
        )
        assert result == {"outcome": "refused", "code": "operation_denied"}
        assert client.submissions == []
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_authoritative_access_refusal_after_submit_dispatch_remains_refused() -> None:
    profile_id = uuid4()
    client = _SubmitClient(profile_id, submit_failure="access")
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call(
            "execute",
            {
                "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                "subject_ref": profile_operation_subject(str(profile_id)),
                "payload": {"kind": "status"},
            },
        )
        assert result == {"outcome": "refused", "code": "operation_denied"}
        assert len(client.submissions) == 1
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_received_period_denial_after_submit_dispatch_is_authoritative_refusal() -> None:
    profile_id = uuid4()
    client = _SubmitClient(profile_id, submit_failure="wire_access")
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call(
            "execute",
            {
                "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                "subject_ref": profile_operation_subject(str(profile_id)),
                "payload": {"kind": "status"},
            },
        )
        assert result == {"outcome": "refused", "code": AccessDenialCode.PERIOD_DENIED.value}
        assert len(client.submissions) == 1
        assert "receipt" not in result and "operation_id" not in result
    finally:
        await adapter.close()
