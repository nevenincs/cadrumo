"""A key the person configured at launch is the only key the server uses, and a refusal of it is asked again."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_mcp.mcp.access_scope import surface_scope
from cadrumo_mcp.mcp.surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES

from .. import runtime_adapter as mcp_runtime
from ..runtime_adapter import RuntimeMcpAdapter
from ..server import build_server
from .admitted_lease import AdmittedLease
from .session import connected_server_and_client_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


_REMOVED_TOOLS = frozenset(
    {"authorization_prepare", "authorization_request", "authorization_poll", "authenticate", "session", "installation"}
)


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [AutomationCustodyCode.MISSING, AutomationCustodyCode.UNAVAILABLE])
async def test_a_refused_configured_key_fences_every_private_route_and_offers_no_way_to_name_another(
    monkeypatch: pytest.MonkeyPatch, failure: AutomationCustodyCode
) -> None:
    profile_id, reference = uuid4(), uuid4()
    calls: list[tuple[UUID, UUID, OperationFrontendProjection]] = []

    async def missing(
        *,
        profile_id: UUID,
        credential_reference: UUID,
        frontend: OperationFrontendProjection,
        timeout: float,
        scope: AccessScope,
    ) -> FrontendClient:
        assert timeout == DEFAULT_TIMEOUT_POLICY.timeout_seconds
        assert scope == surface_scope(MCP_SURFACES[DEFAULT_MCP_SURFACE])
        calls.append((profile_id, credential_reference, frontend))
        raise AutomationCustodyError(failure)

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", missing)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(reference)
        assert calls == [(profile_id, reference, OperationFrontendProjection.EXTERNAL_CLIENT)]
        assert adapter.client is None
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            names = {tool.name for tool in (await sdk.list_tools()).tools}
            # No tool names, requests or presents a credential: the key comes from the launch configuration.
            assert "status" in names
            assert not names & _REMOVED_TOOLS
            status = await sdk.call_tool("status", {})
            assert status.is_error is False
            assert status.structured_content is not None
            assert status.structured_content["authenticated"] is False
            assert status.structured_content["denial"] == failure.value
            for name, args in (
                (
                    "execute",
                    {"definition_id": "auth.local-read", "subject_ref": f"profile:{profile_id}", "payload": {}},
                ),
                ("observe", {"observation": {}}),
                ("result", {"result": {}}),
                ("result_page", {"result": {}, "page": {}}),
                ("review", {"review": {}}),
                ("respond", {"action": "inspect", "operation_id": "x", "interaction_id": "y", "revision": 0}),
                ("control", {"action": "start", "operation_id": "x"}),
            ):
                denied = await sdk.call_tool(name, args)
                assert denied.is_error is True, name
                assert denied.structured_content is not None
                assert denied.structured_content["code"] == failure.value, name
            for name in sorted(_REMOVED_TOOLS):
                absent = await sdk.call_tool(name, {"credential_reference": str(reference)})
                assert absent.is_error is True, name
                assert absent.structured_content == {"outcome": "refused", "code": "unknown_tool"}, name
        # Every call asked the runtime again with the configured key, and with no other.
        assert len(calls) > 1
        assert {call[1] for call in calls} == {reference}
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_a_configured_key_the_runtime_refused_admits_the_server_once_the_runtime_admits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id, reference = uuid4(), uuid4()
    candidate = AdmittedLease(profile_id)
    opened: list[UUID] = []

    async def open_candidate(
        *,
        profile_id: UUID,
        credential_reference: UUID,
        frontend: OperationFrontendProjection,
        timeout: float,
        scope: AccessScope,
    ) -> FrontendClient:
        assert timeout == DEFAULT_TIMEOUT_POLICY.timeout_seconds
        assert scope == surface_scope(MCP_SURFACES[DEFAULT_MCP_SURFACE])
        assert profile_id == candidate.profile_id
        assert frontend is OperationFrontendProjection.EXTERNAL_CLIENT
        assert credential_reference == reference
        opened.append(credential_reference)
        if len(opened) == 1:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return cast(FrontendClient, candidate)

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", open_candidate)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(reference)
        assert adapter.client is None
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            current = await sdk.call_tool("status", {})
            assert current.is_error is False
            assert current.structured_content == {
                "outcome": "status",
                "authenticated": True,
                "grant_required": True,
                "session": "key",
                "surface": "full",
                "status": candidate.status().status.model_dump(mode="json"),
            }
        assert opened == [reference, reference]
        assert adapter.client is candidate
    finally:
        await adapter.close()
