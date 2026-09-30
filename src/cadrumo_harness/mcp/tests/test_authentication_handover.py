"""Adapter session replacement preserves the admitted client on candidate failure."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_harness.mcp import server as mcp_server
from cadrumo_harness.mcp.server import RuntimeMcpAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Client:
    def __init__(self, profile_id: UUID, *, fail_status: bool = False) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.fail_status = fail_status
        self.closed = False

    def status(self) -> SimpleNamespace:
        assert not self.closed
        if self.fail_status:
            raise RuntimeFrontendRefusedError("session_expired")
        return SimpleNamespace(status={"admission": "authorized"})

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [None, "admission", "status"])
async def test_reauthentication_retires_existing_session_only_after_candidate_status(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    profile_id, reference = uuid4(), uuid4()
    original = _Client(profile_id)
    candidate = _Client(profile_id, fail_status=failure == "status")

    async def admit(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> RuntimeFrontendClient:
        assert profile_id == original.profile_id
        assert credential_reference == reference
        assert frontend is OperationFrontendProjection.MCP
        assert not original.closed
        if failure == "admission":
            raise RuntimeFrontendRefusedError("credential_rejected")
        return cast(RuntimeFrontendClient, candidate)

    monkeypatch.setattr(mcp_server, "open_installed_credential_client", admit)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, original))
    try:
        result = await adapter.call("authenticate", {"credential_reference": str(reference)})
        if failure is None:
            assert result == {"outcome": "authenticated", "status": {"admission": "authorized"}}
            assert adapter.client is candidate
            assert original.closed
            assert not candidate.closed
        else:
            assert result == {
                "outcome": "refused",
                "code": "credential_rejected" if failure == "admission" else "session_expired",
            }
            assert adapter.client is original
            assert not original.closed
            assert candidate.closed is (failure == "status")
            assert (await adapter.call("status", {}))["outcome"] == "status"
    finally:
        await adapter.close()
