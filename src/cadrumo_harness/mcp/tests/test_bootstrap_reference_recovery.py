"""A key the person configured at launch is the only key the server uses, and a refusal of it is asked again."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _AdmittedClient:
    """A candidate lease exercising only the adapter's status handover."""

    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.closed = False
        self._status = ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=profile_id,
            session_id=self.session_id,
            session_expires_at=now() + timedelta(minutes=5),
            grant_state=AuthorityState.ACTIVE,
            grant_expires_at=now() + timedelta(minutes=5),
            grant_valid=True,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            effective_scope=AccessScope(
                operations=frozenset(),
                actions=frozenset(),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            denial=None,
        )

    def status(self) -> SimpleNamespace:
        assert not self.closed
        return SimpleNamespace(status=self._status)

    def subscribe_session_retirement(self, receive: object) -> None:
        """The runtime retires no lease of this double."""

    def subscribe_lifecycle_notices(self, receive: object) -> None:
        """The runtime sends this double no lifecycle notice."""

    def close(self) -> None:
        self.closed = True


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
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> RuntimeFrontendClient:
        calls.append((profile_id, credential_reference, frontend))
        raise AutomationCustodyError(failure)

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", missing)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(reference)
        assert calls == [(profile_id, reference, OperationFrontendProjection.MCP)]
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
    candidate = _AdmittedClient(profile_id)
    opened: list[UUID] = []

    async def open_candidate(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> RuntimeFrontendClient:
        assert profile_id == candidate.profile_id
        assert frontend is OperationFrontendProjection.MCP
        assert credential_reference == reference
        opened.append(credential_reference)
        if len(opened) == 1:
            raise AutomationCustodyError(AutomationCustodyCode.UNAVAILABLE)
        return cast(RuntimeFrontendClient, candidate)

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
                "session": "key",
                "surface": "full",
                "status": candidate.status().status.model_dump(mode="json"),
            }
        assert opened == [reference, reference]
        assert adapter.client is candidate
    finally:
        await adapter.close()
