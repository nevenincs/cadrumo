"""MCP result recovery is gated by a real journaled component status."""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import ExitStack
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.operations.journal import OperationJournalRepository
from cadrumo.application.components_operations import COMPONENTS_STATUS_OPERATION_ID
from cadrumo.application.live.verify_capture_operation import VERIFY_TGVI_CAPTURE_DEFINITION_ID
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.operations import OperationEffect, OperationLifecycle, profile_operation_subject
from cadrumo.tests.components_role_package import (
    CountingProxy,
    components_role_fixture,
    counting_proxy_fixture,
    staged_components_role_fixture,
)
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_mcp.mcp.access_scope import surface_scope
from cadrumo_mcp.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_mcp.mcp.server import build_server
from cadrumo_mcp.mcp.surfaces import DEFAULT_MCP_SURFACE, MCP_SURFACES
from cadrumo_mcp.mcp.tests.agent_key_reads import tool_document
from cadrumo_mcp.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime
from dev.runtime_lifecycle.tests.test_components_review import _frontend, _waiting

__all__ = ["components_role_fixture", "counting_proxy_fixture", "staged_components_role_fixture"]
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.external_tool, pytest.mark.windows_only]


@pytest.mark.usefixtures("components_role")
def test_mcp_result_runs_one_status_for_real_missing_browser(tmp_path: Path, counting_proxy: CountingProxy) -> None:
    with service_record_runtime(tmp_path) as runtime, ExitStack() as scope:
        human = _frontend(runtime, OperationFrontendProjection.TUI)
        scope.callback(human.close)
        assert human.login_password(bytearray(PROFILE_INPUT, "utf-8")).status.denial is None
        wire = VerifiedConnection(
            runtime.endpoint.connect(timeout=3),
            expected=ClientHello(product_version="test", storage_identity=runtime.endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
        external = FrontendClient(
            wire,
            profile_id=runtime.profile_id,
            frontend=OperationFrontendProjection.EXTERNAL_CLIENT,
            scope=surface_scope(MCP_SURFACES[DEFAULT_MCP_SURFACE]),
        )
        scope.callback(external.close)
        assert human.attendance_inventory().candidates == ()
        ask = external.request_attendance()
        assert isinstance(ask, AttendancePending)
        assert human.decide_attendance(ask.attendance_id, approve=True).approved
        assert isinstance(external.attendance_status(ask.attendance_id), ProfileStatus)
        adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=external)

        async def scenario() -> None:
            try:
                async with connected_server_and_client_session(build_server(adapter)) as sdk:
                    submitted = tool_document(
                        await sdk.call_tool(
                            "execute",
                            {
                                "definition_id": VERIFY_TGVI_CAPTURE_DEFINITION_ID,
                                "subject_ref": profile_operation_subject(str(runtime.profile_id)),
                                "payload": {"profile_id": str(runtime.profile_id), "nif": "12345678Z"},
                            },
                        )
                    )
                    assert submitted["outcome"] == "submitted", submitted
                    source_id = submitted["receipt"]["operation_id"]

                    async def read() -> OperationPublicProjectionV1:
                        document = tool_document(
                            await sdk.call_tool(
                                "observe",
                                {
                                    "observation": {"operation_id": source_id, "after_cursor": 0, "page_limit": 32},
                                },
                            )
                        )
                        return OperationPublicProjectionV1.model_validate_json(
                            json.dumps(document["reply"]["observation"]["projection"])
                        )

                    source = await _waiting(external, read, target=OperationLifecycle.TERMINAL)
                    assert source.effect is OperationEffect.NONE
                    journal = OperationJournalRepository(storage_root=runtime.root)
                    before = await journal.inventory_page(after=None, limit=128)
                    assert not before.has_more
                    before_snapshots = [await journal.load(entry.operation_id) for entry in before.entries]
                    assert not any(
                        item.identity.definition_id == COMPONENTS_STATUS_OPERATION_ID for item in before_snapshots
                    )
                    response = await sdk.call_tool("result", {"result": {"operation_id": source_id}})
                    assert response.is_error is True
                    reply = response.structured_content
                    assert reply is not None
                    assert reply["recovery_action_id"] == "operator.provision.browser", reply
                    after = await journal.inventory_page(after=None, limit=128)
                    assert not after.has_more
                    snapshots = [await journal.load(entry.operation_id) for entry in after.entries]
                    statuses = [
                        item for item in snapshots if item.identity.definition_id == COMPONENTS_STATUS_OPERATION_ID
                    ]
                    assert len(statuses) == 1
                    status_id = statuses[0].identity.operation_id
                    assert status_id != source_id
                    assert statuses[0].effect is OperationEffect.NONE
                    status_reply = tool_document(await sdk.call_tool("result", {"result": {"operation_id": status_id}}))
                    assert status_reply["document"]["outcome"] == "success"
                    final = await journal.inventory_page(after=None, limit=128)
                    assert {entry.operation_id for entry in final.entries} == {
                        entry.operation_id for entry in after.entries
                    }
                    assert counting_proxy.tunnels == {} and counting_proxy.unauthenticated == 0
            finally:
                await adapter.close()

        asyncio.run(scenario())
