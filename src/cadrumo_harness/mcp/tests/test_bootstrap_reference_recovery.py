"""A failed configured reference leaves public MCP open for explicit recovery."""

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

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [AutomationCustodyCode.MISSING, AutomationCustodyCode.UNAVAILABLE])
async def test_failed_configured_reference_preserves_public_tools_and_fences_every_private_route(
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
    monkeypatch.setattr(mcp_runtime, "authority_query", lambda _args: {"outcome": "published", "report": {}})
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(reference)
        assert calls == [(profile_id, reference, OperationFrontendProjection.MCP)]
        assert adapter.client is None
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            names = {tool.name for tool in (await sdk.list_tools()).tools}
            assert {"status", "authority", "authorization_prepare", "authenticate"} <= names
            status = await sdk.call_tool("status", {})
            assert status.is_error is False
            assert status.structured_content == {
                "outcome": "status",
                "profile_id": str(profile_id),
                "authenticated": False,
                "denial": failure.value,
            }
            published = await sdk.call_tool("authority", {"query": "modelos"})
            assert published.is_error is False
            assert published.structured_content == {"outcome": "published", "report": {}}
            recovery = await sdk.call_tool("authorization_prepare", {"credential_reference": str(reference)})
            assert recovery.is_error is True
            assert recovery.structured_content == {"outcome": "refused", "code": failure.value}
            for name, args in (
                ("search", {"query": "auth.local-read"}),
                ("describe", {"definition_id": "auth.local-read"}),
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
                assert denied.structured_content == {"outcome": "refused", "code": failure.value}, name
        assert calls == [
            (profile_id, reference, OperationFrontendProjection.MCP),
            (profile_id, reference, OperationFrontendProjection.MCP),
        ]
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_explicit_successful_authentication_clears_failed_bootstrap_status_only_after_exact_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id, configured_reference, replacement_reference = uuid4(), uuid4(), uuid4()
    candidate = _AdmittedClient(profile_id)
    opened: list[UUID] = []

    async def open_candidate(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> RuntimeFrontendClient:
        assert profile_id == candidate.profile_id
        assert frontend is OperationFrontendProjection.MCP
        opened.append(credential_reference)
        if credential_reference == configured_reference:
            raise AutomationCustodyError(AutomationCustodyCode.MISSING)
        assert credential_reference == replacement_reference
        return cast(RuntimeFrontendClient, candidate)

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", open_candidate)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(configured_reference)
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            failed_again = await sdk.call_tool("authenticate", {"credential_reference": str(configured_reference)})
            assert failed_again.is_error is True
            assert failed_again.structured_content == {"outcome": "refused", "code": "missing"}
            stale = await sdk.call_tool("status", {})
            assert stale.structured_content == {
                "outcome": "status",
                "profile_id": str(profile_id),
                "authenticated": False,
                "denial": "missing",
            }
            recovered = await sdk.call_tool("authenticate", {"credential_reference": str(replacement_reference)})
            assert recovered.is_error is False
            assert recovered.structured_content == {
                "outcome": "authenticated",
                "status": candidate.status().status.model_dump(mode="json"),
            }
            current = await sdk.call_tool("status", {})
            assert current.is_error is False
            assert current.structured_content == {
                "outcome": "status",
                "status": candidate.status().status.model_dump(mode="json"),
            }
        assert opened == [configured_reference, configured_reference, replacement_reference]
    finally:
        await adapter.close()
    assert candidate.closed
