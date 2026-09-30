"""Lost MCP submit replies cannot be presented as known prewrite refusals."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import RuntimeOperationSubmit
from cadrumo_harness.mcp.server import RuntimeMcpAdapter, build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


class _SubmitClient:
    def __init__(self, profile_id: UUID, *, fail_description: bool = False) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.fail_description = fail_description
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
        raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_lost_submit_reply_is_unresolved_with_only_safe_request_correlation() -> None:
    profile_id = uuid4()
    client = _SubmitClient(profile_id)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            submitted = await sdk.call_tool(
                "execute",
                {"definition_id": "auth.read", "subject_ref": f"profile:{profile_id}", "payload": {"kind": "status"}},
            )
            assert submitted.is_error is True
            result = submitted.structured_content
            assert result is not None
            assert result["outcome"] == "unresolved"
            assert result["code"] == RuntimeRefusalCode.DEADLINE_EXCEEDED.value
            assert result["definition_id"] == "auth.read"
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
            {"definition_id": "auth.read", "subject_ref": f"profile:{profile_id}", "payload": {"kind": "status"}},
        )
        assert result == {"outcome": "refused", "code": "operation_denied"}
        assert client.submissions == []
    finally:
        await adapter.close()
