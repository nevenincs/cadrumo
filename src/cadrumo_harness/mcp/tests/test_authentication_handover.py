"""Adapter session replacement preserves the admitted client on candidate failure."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessScope,
    Availability,
    ProfileAccessStatus,
)
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp import server as mcp_server
from cadrumo_harness.mcp.server import RuntimeMcpAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Client:
    def __init__(self, profile_id: UUID, *, fail_status: bool = False, status_flaw: str | None = None) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.session_expires_at = now() + timedelta(minutes=5)
        self.fail_status = fail_status
        self.status_flaw = status_flaw
        self.closed = False

    def status(self) -> SimpleNamespace:
        assert not self.closed
        if self.fail_status:
            raise RuntimeFrontendRefusedError("session_expired")
        status = ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=self.profile_id,
            session_id=self.session_id,
            session_expires_at=self.session_expires_at,
            grant_state=None,
            grant_expires_at=None,
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
        if self.status_flaw == "denial":
            status = status.model_copy(update={"denial": AccessDenialCode.SESSION_EXPIRED})
        elif self.status_flaw == "profile":
            status = status.model_copy(update={"profile_id": uuid4()})
        elif self.status_flaw == "session":
            status = status.model_copy(update={"session_id": uuid4()})
        elif self.status_flaw == "expired":
            status = status.model_copy(update={"session_expires_at": now() - timedelta(seconds=1)})
        elif self.status_flaw == "grant":
            status = status.model_copy(update={"grant_valid": False})
        return SimpleNamespace(status=status)

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [None, "admission", "status", "denial", "profile", "session", "expired", "grant"])
async def test_reauthentication_retires_existing_session_only_after_candidate_status(
    monkeypatch: pytest.MonkeyPatch, failure: str | None
) -> None:
    profile_id, reference = uuid4(), uuid4()
    original = _Client(profile_id)
    candidate = _Client(
        profile_id,
        fail_status=failure == "status",
        status_flaw=failure if failure in {"denial", "profile", "session", "expired", "grant"} else None,
    )

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
            assert result == {"outcome": "authenticated", "status": candidate.status().status.model_dump(mode="json")}
            assert adapter.client is candidate
            assert original.closed
            assert not candidate.closed
        else:
            assert result == {
                "outcome": "refused",
                "code": (
                    "credential_rejected"
                    if failure == "admission"
                    else "profile_mismatch"
                    if failure in {"profile", "session"}
                    else "grant_inactive"
                    if failure == "grant"
                    else "session_expired"
                ),
            }
            assert adapter.client is original
            assert not original.closed
            assert candidate.closed is (failure != "admission")
            assert (await adapter.call("status", {}))["outcome"] == "status"
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_search_refuses_expired_admission_before_listing_private_operations() -> None:
    profile_id = uuid4()
    expired = _Client(profile_id, status_flaw="expired")
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, expired))
    try:
        assert await adapter.call("search", {}) == {"outcome": "refused", "code": "session_expired"}
    finally:
        await adapter.close()
