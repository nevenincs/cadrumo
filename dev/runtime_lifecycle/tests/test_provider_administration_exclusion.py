"""Historical provider administration belongs to the agent service, outside the runtime catalogue.

Real native clients and MCP keep valid sessions when the retired tax operations
are refused. Credential administration is owned by cadrumo-agent-service; its
catalog adapter tests exercise service-owned catalog loading.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Final
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import AccessDenialCode
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.core.config import override_settings
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo.entrypoints.operation_composition import build_manifest_operation_registry
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.operation_access import OperationRequest, OperationSubmit
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_harness.mcp.access_scope import surface_scope
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.surfaces import MCP_SURFACES, McpSurfaceName
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.host.tests.stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker and protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

# Historical wire identifiers are test data, never a supported compatibility API.
_CHANGES: Final = ("provider-settings.set", "provider-settings.remove", "provider-settings.reset")
_STATUS: Final = "provider-settings.status"
_LANE: Final = "synthetic-lane"
_PERSON_FRONTENDS: Final = (OperationFrontendProjection.CLI, OperationFrontendProjection.TUI)


def _resumed(runtime: StoredSignInRuntime, frontend: OperationFrontendProjection) -> FrontendClient:
    """Resume one genuine person session over the verified native connection."""
    client = FrontendClient(runtime.connect(), profile_id=runtime.profile_id, frontend=frontend)
    client.resume_receipt()
    return client


def _refused(call: Callable[[], object], expected: str) -> None:
    with pytest.raises(FrontendRefusedError) as refused:
        call()
    assert refused.value.reason == expected, (refused.value.reason, refused.value.request_faults)


def _payload(runtime: StoredSignInRuntime) -> dict[str, str]:
    return {
        "profile_id": str(runtime.profile_id),
        "provider_id": _LANE,
        "expected_revision": ABSENT_SECURE_OBJECT_REVISION_ID,
    }


def _change(runtime: StoredSignInRuntime, client: FrontendClient, definition_id: str) -> OperationSubmit:
    return OperationSubmit(
        request_id=uuid4(),
        profile_id=runtime.profile_id,
        session_id=client.session_id,
        definition_id=definition_id,
        subject_ref=f"profile:{runtime.profile_id}",
        payload_json=json.dumps(_payload(runtime)),
    )


def _absent_for_client(runtime: StoredSignInRuntime, client: FrontendClient, definition_id: str) -> None:
    session_id = client.session_id
    scope = client.status().status.effective_scope
    assert definition_id not in scope.operations and _STATUS not in scope.operations
    # Describe checks the admitted scope before requesting a worker contract.
    _refused(
        lambda: client.describe(definition_id, deadline=time.monotonic() + 30), AccessDenialCode.OPERATION_DENIED.value
    )
    # Small submissions reach worker contract validation before payload decoding.
    submitted = _change(runtime, client, definition_id)
    _refused(
        lambda: client.operation(submitted, deadline=time.monotonic() + 30),
        AutomationCustodyCode.CREDENTIAL_REJECTED.value,
    )
    _refused(lambda: client.describe(_STATUS, deadline=time.monotonic() + 30), AccessDenialCode.OPERATION_DENIED.value)
    status = client.status().status
    assert status.denial is None and status.session_id == session_id


@pytest.mark.parametrize("definition_id", _CHANGES)
def test_no_frontend_catalogue_contains_historical_provider_administration(definition_id: str) -> None:
    contracts = build_manifest_operation_registry().public_contract_set.definitions
    admitted = {contract.definition_id for contract in contracts}
    for frontend in OperationFrontendProjection:
        assert definition_id not in admitted, frontend
        assert _STATUS not in admitted, frontend


@pytest.mark.parametrize("definition_id", _CHANGES)
def test_native_person_and_attended_agent_sessions_refuse_provider_administration(
    definition_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        for frontend in _PERSON_FRONTENDS:
            person = _resumed(runtime, frontend)
            try:
                _absent_for_client(runtime, person, definition_id)
            finally:
                person.close()
        person = _resumed(runtime, OperationFrontendProjection.CLI)
        initial_inventory = person.attendance_inventory()
        assert initial_inventory.profile_id == runtime.profile_id and initial_inventory.candidates == ()
        automation = FrontendClient(
            runtime.connect(),
            profile_id=runtime.profile_id,
            frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
            scope=surface_scope(MCP_SURFACES[McpSurfaceName.FULL]),
        )
        try:
            pending = automation.request_attendance()
            assert isinstance(pending, AttendancePending)
            (candidate,) = person.attendance_inventory().candidates
            assert candidate.attendance_id == pending.attendance_id and candidate.process_id == os.getpid()
            assert person.decide_attendance(pending.attendance_id, approve=True).approved
            admitted = automation.attendance_status(pending.attendance_id)
            assert isinstance(admitted, ProfileStatus) and admitted.status.denial is None
            _absent_for_client(runtime, automation, definition_id)
            assert person.status().status.denial is None
        finally:
            automation.close()
            person.close()


@pytest.mark.anyio
@pytest.mark.parametrize("definition_id", _CHANGES)
async def test_mcp_refuses_provider_administration_at_description_before_submission(
    definition_id: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with (
        stored_sign_in_runtime(tmp_path, monkeypatch) as runtime,
        override_settings(cadrumo_active_profile=str(runtime.profile_id)),
    ):
        handed: list[str] = []
        handle = runtime.profiles.operation

        def kept(context: ConnectionContext, channel: ByteChannel, request: OperationRequest) -> None:
            handed.append(request.action)
            handle(context, channel, request)

        person = _resumed(runtime, OperationFrontendProjection.CLI)
        adapter = RuntimeMcpAdapter(profile_id=None, client=None, requests_attendance=True)
        asking = asyncio.create_task(adapter.call("status", {}))
        try:
            deadline = time.monotonic() + 30
            while True:
                inventory = await asyncio.to_thread(person.attendance_inventory)
                if inventory.candidates:
                    (candidate,) = inventory.candidates
                    assert candidate.process_id == os.getpid()
                    decision = await asyncio.to_thread(person.decide_attendance, candidate.attendance_id, approve=True)
                    assert decision.approved
                    break
                assert not asking.done(), "the adapter answered before attendance approval"
                assert time.monotonic() < deadline, "the adapter made no native attendance ask"
                await asyncio.sleep(0.01)
            status = await asking
            assert status["session"] == "attended"
            assert adapter.client is not None
            session_id = adapter.client.session_id
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                monkeypatch.setattr(runtime.profiles, "operation", kept)
                answer = await sdk.call_tool("execute", {"definition_id": definition_id, "payload": _payload(runtime)})
                assert answer.is_error is True
                assert answer.structured_content is not None
                assert answer.structured_content["outcome"] == "refused"
                assert answer.structured_content["code"] == AccessDenialCode.OPERATION_DENIED.value
                assert not any("submit" in action for action in handed), handed
                assert "operation_contract" in handed
                assert adapter.client is not None
                retained = (await asyncio.to_thread(adapter.client.status)).status
                assert retained.denial is None and retained.session_id == session_id
                assert (await asyncio.to_thread(person.status)).status.denial is None
        finally:
            if not asking.done():
                asking.cancel()
                with suppress(asyncio.CancelledError):
                    await asking
            await adapter.close()
            await asyncio.to_thread(person.close)
