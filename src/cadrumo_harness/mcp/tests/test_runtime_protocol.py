"""Protocol checks for a fresh, unauthenticated exact-profile adapter."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp import server as mcp_server
from cadrumo_harness.mcp.server import RuntimeMcpAdapter, build_server
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
        assert {
            "status",
            "authorization_prepare",
            "authenticate",
            "search",
            "execute",
            "result",
            "respond",
        } <= set(names)

        status = await client.call_tool("status", {})
        assert status.is_error is False
        assert status.structured_content == {
            "outcome": "status",
            "profile_id": str(profile_id),
            "authenticated": False,
            "denial": "authentication_required",
        }

        private = await client.call_tool("search", {})
        assert private.is_error is True
        assert private.structured_content == {"outcome": "refused", "code": "authentication_required"}

        invalid = await client.call_tool("control", {"action": "erase", "operation_id": "unsafe"})
        assert invalid.is_error is True
        assert invalid.structured_content == {"outcome": "refused", "code": "invalid_request"}
    await adapter.close()


class _RuntimeClientStub:
    """One exact frontend connection with observable close ownership."""

    def __init__(self, profile_id: UUID, enrollment: object) -> None:
        self.profile_id = profile_id
        self.frontend = OperationFrontendProjection.MCP
        self.enrollment = enrollment
        self.close_count = 0
        self.enroll_calls = 0
        self.grant_change_calls = 0

    def prepare_enrollment(self, _secret_store: object) -> object:
        self.enroll_calls += 1
        return self.enrollment

    def prepare_grant_change(self, _secret_store: object) -> object:
        self.grant_change_calls += 1
        return self.enrollment

    def status(self) -> SimpleNamespace:
        return SimpleNamespace(status={"admission": "authorized"})

    def close(self) -> None:
        self.close_count += 1


@pytest.mark.anyio
async def test_authenticate_admits_exact_profile_for_mcp_and_close_releases_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    credential_reference = uuid4()
    admitted = _RuntimeClientStub(profile_id, enrollment=None)
    opened: list[tuple[UUID, UUID, OperationFrontendProjection]] = []

    async def open_credential_client(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> _RuntimeClientStub:
        opened.append((profile_id, credential_reference, frontend))
        return admitted

    monkeypatch.setattr(mcp_server, "open_installed_credential_client", open_credential_client)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as client:
            authenticated = await client.call_tool("authenticate", {"credential_reference": str(credential_reference)})
            assert authenticated.is_error is False
            assert authenticated.structured_content == {
                "outcome": "authenticated",
                "status": {"admission": "authorized"},
            }
            status = await client.call_tool("status", {})
            assert status.is_error is False
            assert status.structured_content == {
                "outcome": "status",
                "status": {"admission": "authorized"},
            }
            assert adapter.client is admitted

        assert opened == [(profile_id, credential_reference, OperationFrontendProjection.MCP)]
    finally:
        await adapter.close()
    assert admitted.close_count == 1


def _enrollment_stub(*, stage: EnrollmentStage | None, expires_at: datetime) -> SimpleNamespace:
    """Provide only the safe receipt stage and prepared replacement identity."""
    prepared = SimpleNamespace(
        enrollment_request_id=uuid4(),
        client_id=uuid4(),
        destination_id=uuid4(),
        expires_at=expires_at,
    )
    receipt = None if stage is None else SimpleNamespace(stage=stage)
    return SimpleNamespace(prepared=prepared, receipt=receipt)


@pytest.mark.anyio
async def test_authorization_prepare_keeps_live_pending_enrollment_and_admitted_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    admitted = _RuntimeClientStub(profile_id, enrollment=None)
    old_enrollment = _RuntimeClientStub(
        profile_id,
        enrollment=_enrollment_stub(stage=EnrollmentStage.REQUESTED, expires_at=now() + timedelta(minutes=2)),
    )
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, admitted))
    adapter._enrollment_client = cast(RuntimeFrontendClient, old_enrollment)
    adapter._enrollment = cast(NativeEnrollmentClient, old_enrollment.enrollment)
    opened: list[_RuntimeClientStub] = []

    async def open_client(*, profile_id: UUID, frontend: OperationFrontendProjection) -> _RuntimeClientStub:
        assert profile_id == adapter.profile_id
        assert frontend is OperationFrontendProjection.MCP
        replacement = _RuntimeClientStub(profile_id, enrollment=_enrollment_stub(stage=None, expires_at=now()))
        opened.append(replacement)
        return replacement

    monkeypatch.setattr(mcp_server, "open_installed_runtime_client", open_client)
    try:
        result = await adapter.call("authorization_prepare", {})
        assert result == {"outcome": "refused", "code": "invalid_request"}
        assert opened == []
        assert adapter._enrollment_client is old_enrollment
        assert old_enrollment.close_count == 0
        assert adapter.client is admitted
        assert admitted.close_count == 0
    finally:
        await adapter.close()


@pytest.mark.parametrize(
    ("stage", "expired"),
    (
        (EnrollmentStage.COMPLETE, False),
        (EnrollmentStage.DECLINED, False),
        (EnrollmentStage.REQUESTED, True),
    ),
)
@pytest.mark.anyio
async def test_authorization_prepare_retires_only_finished_or_expired_enrollment(
    monkeypatch: pytest.MonkeyPatch, stage: EnrollmentStage, expired: bool
) -> None:
    profile_id = uuid4()
    admitted = _RuntimeClientStub(profile_id, enrollment=None)
    expires_at = now() - timedelta(seconds=1) if expired else now() + timedelta(minutes=2)
    old_enrollment = _RuntimeClientStub(
        profile_id,
        enrollment=_enrollment_stub(stage=stage, expires_at=expires_at),
    )
    replacement_enrollment = _enrollment_stub(stage=None, expires_at=now() + timedelta(minutes=2))
    replacement = _RuntimeClientStub(profile_id, enrollment=replacement_enrollment)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, admitted))
    adapter._enrollment_client = cast(RuntimeFrontendClient, old_enrollment)
    adapter._enrollment = cast(NativeEnrollmentClient, old_enrollment.enrollment)
    opened: list[_RuntimeClientStub] = []

    async def open_client(*, profile_id: UUID, frontend: OperationFrontendProjection) -> _RuntimeClientStub:
        assert profile_id == adapter.profile_id
        assert frontend is OperationFrontendProjection.MCP
        opened.append(replacement)
        return replacement

    monkeypatch.setattr(mcp_server, "open_installed_runtime_client", open_client)
    try:
        result = await adapter.call("authorization_prepare", {})
        assert result == {
            "outcome": "prepared",
            "profile_id": str(profile_id),
            "request_id": str(replacement_enrollment.prepared.enrollment_request_id),
            "client_id": str(replacement_enrollment.prepared.client_id),
            "destination_id": str(replacement_enrollment.prepared.destination_id),
            "expires_at": replacement_enrollment.prepared.expires_at.isoformat(),
        }
        assert opened == [replacement]
        assert old_enrollment.close_count == 1
        assert adapter._enrollment_client is replacement
        assert adapter._enrollment is replacement_enrollment
        assert adapter.client is admitted
        assert admitted.close_count == 0
        assert replacement.close_count == 0
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_authorization_prepare_routes_own_grant_change_without_closing_admitted_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile_id = uuid4()
    credential_reference = uuid4()
    admitted = _RuntimeClientStub(profile_id, enrollment=None)
    prepared_enrollment = _enrollment_stub(stage=None, expires_at=now() + timedelta(minutes=2))
    request_client = _RuntimeClientStub(profile_id, enrollment=prepared_enrollment)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=cast(RuntimeFrontendClient, admitted))
    opened_credentials: list[tuple[UUID, OperationFrontendProjection]] = []
    opened_uncredentialed: list[UUID] = []

    async def open_credential_client(
        *, profile_id: UUID, credential_reference: UUID, frontend: OperationFrontendProjection
    ) -> _RuntimeClientStub:
        opened_credentials.append((credential_reference, frontend))
        return request_client

    async def open_uncredentialed_client(
        *, profile_id: UUID, frontend: OperationFrontendProjection
    ) -> _RuntimeClientStub:
        opened_uncredentialed.append(profile_id)
        return request_client

    monkeypatch.setattr(mcp_server, "open_installed_credential_client", open_credential_client)
    monkeypatch.setattr(mcp_server, "open_installed_runtime_client", open_uncredentialed_client)
    try:
        result = await adapter.call("authorization_prepare", {"credential_reference": str(credential_reference)})
        assert result["outcome"] == "prepared"
        assert opened_credentials == [(credential_reference, OperationFrontendProjection.MCP)]
        assert opened_uncredentialed == []
        assert request_client.grant_change_calls == 1
        assert request_client.enroll_calls == 0
        assert adapter._enrollment_client is request_client
        assert adapter.client is admitted
        assert admitted.close_count == 0
        assert request_client.close_count == 0
    finally:
        await adapter.close()
