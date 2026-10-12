"""Protocol checks for a fresh, unauthenticated exact-profile adapter."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessScope,
    AuthorityState,
    Availability,
    EffectiveScopeSummary,
    ProfileAccessStatus,
)
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.protocol_contract import SIGN_IN_REMEDY
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


@pytest.mark.anyio
async def test_fresh_adapter_orients_without_claiming_profile_access() -> None:
    profile_id = uuid4()
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    async with connected_server_and_client_session(build_server(adapter)) as client:
        advertised_tools = (await client.list_tools()).tools
        names = [tool.name for tool in advertised_tools]
        assert len(names) == len(set(names))
        assert {"status", "search", "execute", "result", "respond"} <= set(names)
        # No tool signs in, names a key, requests one, or acts outside the profile.
        assert not {
            "authorization_prepare",
            "authorization_request",
            "authorization_poll",
            "authenticate",
            "session",
            "installation",
        } & set(names)

        status = await client.call_tool("status", {})
        assert status.is_error is False
        assert status.structured_content == {
            "outcome": "status",
            "profile_id": str(profile_id),
            "authenticated": False,
            "session": "none",
            "surface": "full",
            "denial": "authentication_required",
            "remedy": SIGN_IN_REMEDY,
        }

        private = await client.call_tool("observe", {"observation": {}})
        assert private.is_error is True
        assert private.structured_content == {
            "outcome": "refused",
            "code": "authentication_required",
            "remedy": SIGN_IN_REMEDY,
        }

        invalid = await client.call_tool("control", {"action": "erase", "operation_id": "unsafe"})
        assert invalid.is_error is True
        assert invalid.structured_content == {"outcome": "refused", "code": "invalid_request"}
    await adapter.close()


class _RuntimeClientStub:
    """One exact frontend connection with observable close ownership."""

    def __init__(self, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.session_expires_at = now() + timedelta(minutes=5)
        self.close_count = 0

    def status(self) -> SimpleNamespace:
        return SimpleNamespace(
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=self.session_expires_at,
                grant_state=AuthorityState.ACTIVE,
                grant_expires_at=self.session_expires_at,
                grant_valid=True,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.AVAILABLE,
                published_authority=Availability.AVAILABLE,
                provider=Availability.NOT_REQUIRED,
                effective_scope=EffectiveScopeSummary.summarize(
                    AccessScope(
                        operations=frozenset(),
                        actions=frozenset(),
                        disclosures=frozenset(),
                        periods=None,
                        allow_period_independent=True,
                        allow_delegation=False,
                    )
                ),
                denial=None,
            )
        )

    def subscribe_session_retirement(self, receive: object) -> None:
        """The runtime retires no lease of this double."""

    def subscribe_lifecycle_notices(self, receive: object) -> None:
        """The runtime sends this double no lifecycle notice."""

    def close(self) -> None:
        self.close_count += 1


@pytest.mark.anyio
async def test_the_configured_key_admits_exact_profile_for_mcp_and_close_releases_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    credential_reference = uuid4()
    admitted = _RuntimeClientStub(profile_id)
    opened: list[tuple[UUID, UUID, OperationFrontendProjection]] = []

    async def open_credential_client(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> _RuntimeClientStub:
        opened.append((profile_id, credential_reference, frontend))
        return admitted

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", open_credential_client)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(credential_reference)
        async with connected_server_and_client_session(build_server(adapter)) as client:
            status = await client.call_tool("status", {})
            assert status.is_error is False
            assert status.structured_content == {
                "outcome": "status",
                "session": "key",
                "surface": "full",
                "status": admitted.status().status.model_dump(mode="json"),
            }
            assert adapter.client is admitted

        assert opened == [(profile_id, credential_reference, OperationFrontendProjection.MCP)]
    finally:
        await adapter.close()
    assert admitted.close_count == 1
