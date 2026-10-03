"""Adapter session replacement preserves the admitted client on candidate failure."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessScope,
    AuthorityState,
    Availability,
    ProfileAccessStatus,
)
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp import runtime_admission as mcp_admission
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AT = datetime(2026, 10, 3, 12, tzinfo=UTC)
_STATUS_REFUSALS = (
    ("denial", "grant_expired"),
    ("profile", "profile_mismatch"),
    ("session", "profile_mismatch"),
    ("disconnected", "profile_mismatch"),
    ("unbound", "profile_mismatch"),
    ("unauthenticated", "profile_mismatch"),
    ("session_missing_expiry", "session_expired"),
    ("session_at_expiry", "session_expired"),
    ("expired", "session_expired"),
    ("grant", "grant_inactive"),
    ("grant_missing_state", "grant_inactive"),
    ("grant_pending", "grant_inactive"),
    ("grant_suspended", "grant_inactive"),
    ("grant_revoked", "grant_inactive"),
    ("grant_missing_expiry", "grant_inactive"),
    ("grant_at_expiry", "grant_inactive"),
    ("grant_expired", "grant_inactive"),
    ("client_session_swapped", "profile_mismatch"),
    ("client_profile_swapped", "profile_mismatch"),
    ("client_frontend_swapped", "profile_mismatch"),
)


class _Client:
    def __init__(
        self, profile_id: UUID, *, fail_status: bool = False, status_flaw: str | None = None, at: datetime | None = None
    ) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.session_id = uuid4()
        self.at = now() if at is None else at
        self.session_expires_at = self.at + timedelta(minutes=5)
        self.fail_status = fail_status
        self.status_flaw = status_flaw
        self.close_count = 0
        self.status_calls = 0
        self.describe_calls: list[str] = []

    @property
    def closed(self) -> bool:
        return self.close_count != 0

    def status(self) -> SimpleNamespace:
        assert not self.closed
        self.status_calls += 1
        if self.fail_status:
            raise RuntimeFrontendRefusedError("session_expired")
        status = ProfileAccessStatus(
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
            effective_scope=AccessScope(
                operations=frozenset({"auth.local-read"}),
                actions=frozenset(),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
            denial=None,
        )
        flaws = {
            "denial": {
                "denial": AccessDenialCode.GRANT_EXPIRED,
                "session_expires_at": None,
                "grant_valid": False,
                "profile_id": uuid4(),
            },
            "profile": {"profile_id": uuid4(), "grant_state": None},
            "session": {"session_id": uuid4(), "grant_state": None},
            "disconnected": {"connected": False, "grant_state": None},
            "unbound": {"profile_bound": False, "grant_state": None},
            "unauthenticated": {"credential_authenticated": False, "grant_state": None},
            "session_missing_expiry": {"session_expires_at": None, "grant_valid": False, "profile_id": uuid4()},
            "session_at_expiry": {"session_expires_at": self.at},
            "expired": {"session_expires_at": self.at - timedelta(seconds=1), "grant_valid": False},
            "grant": {"grant_valid": False, "profile_id": uuid4()},
            "grant_missing_state": {"grant_state": None},
            "grant_pending": {"grant_state": AuthorityState.PENDING},
            "grant_suspended": {"grant_state": AuthorityState.SUSPENDED},
            "grant_revoked": {"grant_state": AuthorityState.REVOKED},
            "grant_missing_expiry": {"grant_expires_at": None},
            "grant_at_expiry": {"grant_expires_at": self.at},
            "grant_expired": {"grant_expires_at": self.at - timedelta(seconds=1)},
        }
        status = status.model_copy(update=flaws.get(self.status_flaw or "", {}))
        if self.status_flaw == "client_session_swapped":
            self.session_id = uuid4()
        elif self.status_flaw == "client_profile_swapped":
            self.profile_id = uuid4()
        elif self.status_flaw == "client_frontend_swapped":
            self.frontend = OperationFrontendProjection.TUI
        return SimpleNamespace(status=status)

    def describe(self, definition_id: str, *, deadline: float) -> SimpleNamespace:
        assert not self.closed
        assert deadline > 0
        self.describe_calls.append(definition_id)
        return SimpleNamespace(contract={"definition_id": definition_id})

    def close(self) -> None:
        self.close_count += 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failure", "expected_code"),
    ((None, None), ("admission", "credential_rejected"), ("status", "session_expired"), *_STATUS_REFUSALS),
)
async def test_reauthentication_retires_existing_session_only_after_candidate_status(
    monkeypatch: pytest.MonkeyPatch, failure: str | None, expected_code: str | None
) -> None:
    monkeypatch.setattr(mcp_admission, "now", lambda: _AT)
    profile_id, reference = uuid4(), uuid4()
    original = _Client(profile_id, at=_AT)
    original_session = original.session_id
    candidate = _Client(
        profile_id,
        fail_status=failure == "status",
        status_flaw=failure,
        at=_AT,
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

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", admit)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, original))
    try:
        result = await adapter.call("authenticate", {"credential_reference": str(reference)})
        if failure is None:
            assert result == {"outcome": "authenticated", "status": candidate.status().status.model_dump(mode="json")}
            assert adapter.client is candidate
            assert original.close_count == 1
            assert candidate.close_count == 0
        else:
            assert result == {
                "outcome": "refused",
                "code": expected_code,
            }
            assert adapter.client is original
            assert original.close_count == 0
            assert original.session_id == original_session
            assert candidate.close_count == (0 if failure == "admission" else 1)
            assert (await adapter.call("status", {}))["outcome"] == "status"
            assert await adapter.call("search", {}) == {
                "outcome": "found",
                "operations": [{"definition_id": "auth.local-read"}],
            }
            assert original.describe_calls == ["auth.local-read"]
            assert candidate.describe_calls == []
    finally:
        await adapter.close()
    assert original.close_count == 1
    assert candidate.close_count == (0 if failure == "admission" else 1)


@pytest.mark.anyio
@pytest.mark.parametrize(("status_flaw", "expected_code"), ((None, None), *_STATUS_REFUSALS))
async def test_search_requires_exact_live_admission_before_listing_private_operations(
    monkeypatch: pytest.MonkeyPatch, status_flaw: str | None, expected_code: str | None
) -> None:
    profile_id = uuid4()
    client = _Client(profile_id, status_flaw=status_flaw, at=_AT)
    samples: list[datetime] = []

    def sample_after_status() -> datetime:
        assert client.status_calls == 1
        samples.append(_AT)
        return _AT

    monkeypatch.setattr(mcp_admission, "now", sample_after_status)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        result = await adapter.call("search", {})
        if expected_code is None:
            assert result == {"outcome": "found", "operations": [{"definition_id": "auth.local-read"}]}
            assert client.describe_calls == ["auth.local-read"]
        else:
            assert result == {"outcome": "refused", "code": expected_code}
            assert client.describe_calls == []
        assert samples == [_AT]
        assert client.close_count == 0
    finally:
        await adapter.close()
    assert client.close_count == 1
