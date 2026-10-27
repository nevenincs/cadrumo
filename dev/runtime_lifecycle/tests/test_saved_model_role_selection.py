"""Desktop administration persists the choice CLI, TUI and MCP operations read.

This joins the authenticated desktop admin protocol, agent service, encrypted
runtime custody and both production relays. Installed-image verification and
the upstream agent catalogue are explicit test ports. The CLI registered
runner, TUI controller and MCP protocol each submit and read the real report
operation. Visual UI automation and native desktop invocation are outside
this boundary.
"""

from __future__ import annotations

import asyncio
import json
import socket
import struct
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    EXTENSION_SETTINGS_NAMESPACE,
    MODEL_ROLE_SELECTIONS_NAMESPACE,
)
from cadrumo.application.local_reader_contracts import LOCAL_READER_OPERATION_SUBJECT
from cadrumo.application.local_reader_report import (
    LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
    LocalReaderReportPublicResultV1,
    LocalReaderReportRequest,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.schema_identity import OperationSchemaIdentityV1
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_agent_service.adapters.agent_provider_catalog import AgentProviderCatalogSource
from cadrumo_agent_service.admin import AdminServer
from cadrumo_agent_service.host.model_run_relay import ModelRunRelay
from cadrumo_agent_service.providers.application.ports import StoredModelRoleSelections
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import synthetic_catalog
from cadrumo_agent_service.providers.domain.catalog import ProviderCatalog
from cadrumo_agent_service.providers.persistence.store import (
    MODEL_ROLE_SELECTIONS_CAPABILITY,
    PROVIDER_RECORD_CAPABILITY,
    SecureModelRoleSelectionsStore,
)
from cadrumo_agent_service.service import AgentService
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.contracts.access_vocabulary import AccessAction, AccessScope
from cadrumo_client.contracts.attendance import AttendancePending
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.extension_records import ExtensionRecordCapability
from cadrumo_client.contracts.model_runs import (
    MODEL_RUN_LANE_ID_PATTERN,
    ModelRunOutcome,
    ModelRunRefusalCode,
    ModelRunSelectedModel,
)
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.operation_changes import AsyncOperationChanges
from cadrumo_client.transport.operation_controller import OperationController, await_terminal_projection
from cadrumo_mcp.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_mcp.mcp.server import build_server
from cadrumo_mcp.mcp.tests.agent_key_reads import tool_document
from cadrumo_mcp.mcp.tests.session import connected_server_and_client_session
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.contracts.worker_authorization import WorkerModelRun
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]


def _capability(name: str) -> ExtensionRecordCapability:
    selections = name == MODEL_ROLE_SELECTIONS_CAPABILITY
    namespace = MODEL_ROLE_SELECTIONS_NAMESPACE if selections else EXTENSION_SETTINGS_NAMESPACE
    return ExtensionRecordCapability(
        capability=name,
        namespace=namespace.namespace,
        schema_version=namespace.schema_version,
        classification=namespace.sensitivity,
        key_pattern=r"^selections$" if selections else MODEL_RUN_LANE_ID_PATTERN,
        maximum_bytes=32768,
        actions=frozenset({"read", "write", "delete", "generation"}),
    )


def _send(stream: socket.socket, data: bytes) -> None:
    stream.sendall(struct.pack("!I", len(data)) + data)


def _exact(stream: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        part = stream.recv(count - len(data))
        if not part:
            raise EOFError("incomplete admin response")
        data.extend(part)
    return bytes(data)


def _admin(server: AdminServer, bearer: bytes, action: str, **arguments: str) -> dict[str, Any]:
    request = {"version": 1, "request_id": str(uuid4()), "action": action, **arguments}
    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as stream:
        _send(stream, bearer)
        _send(stream, json.dumps(request).encode())
        (size,) = struct.unpack("!I", _exact(stream, 4))
        response = json.loads(_exact(stream, size))
    assert response["request_id"] == request["request_id"]
    return response["result"]


async def _tui_report(frontend: FrontendClient) -> LocalReaderReportPublicResultV1:
    controller = await OperationController.submit(
        frontend,
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        payload=LocalReaderReportRequest(),
    )
    await controller.start()
    projection = await await_terminal_projection(
        controller,
        definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
        subject_ref=LOCAL_READER_OPERATION_SUBJECT,
        request_schema=OperationSchemaIdentityV1.from_model(
            schema_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID + ".request",
            schema_version=1,
            model_type=LocalReaderReportRequest,
        ),
        deadline=time.monotonic() + 120,
    )
    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, projection
    return await controller.read_settled_result(
        projection,
        LocalReaderReportPublicResultV1,
        result_version=1,
    )


async def _mcp_report(adapter: RuntimeMcpAdapter, frontend: FrontendClient) -> LocalReaderReportPublicResultV1:
    async with connected_server_and_client_session(build_server(adapter)) as sdk:
        submitted = tool_document(
            await sdk.call_tool(
                "execute",
                {
                    "definition_id": LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
                    "subject_ref": LOCAL_READER_OPERATION_SUBJECT,
                    "payload": {},
                },
            )
        )
        operation_id = submitted["receipt"]["operation_id"]
        deadline = time.monotonic() + 120
        with AsyncOperationChanges(frontend) as changes:
            while True:
                changes.arm()
                observed = tool_document(
                    await sdk.call_tool(
                        "observe",
                        {
                            "observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32},
                        },
                    )
                )
                projection = observed["reply"]["observation"]["projection"]
                if projection["lifecycle"] == "terminal":
                    break
                remaining = deadline - time.monotonic()
                assert remaining > 0, observed
                await changes.wait(remaining)
        assert projection["terminal_condition"] == "succeeded", projection
        result = tool_document(await sdk.call_tool("result", {"result": {"operation_id": operation_id}}))
        assert result["document"]["outcome"] == "success", result
        return LocalReaderReportPublicResultV1.model_validate_json(json.dumps(result["document"]["projection"]))


@pytest.mark.parametrize(
    "projection",
    [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.EXTERNAL_CLIENT],
)
def test_authenticated_desktop_choice_survives_new_store_and_runtime_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    projection: OperationFrontendProjection,
) -> None:
    def declared_catalog(self: AgentProviderCatalogSource) -> ProviderCatalog:
        return synthetic_catalog()

    monkeypatch.setattr(AgentProviderCatalogSource, "catalog", declared_catalog)
    capabilities = tuple(_capability(name) for name in (MODEL_ROLE_SELECTIONS_CAPABILITY, PROVIDER_RECORD_CAPABILITY))
    with (
        service_record_runtime(tmp_path, record_capabilities=capabilities, model_runs=True) as runtime,
        ExitStack() as scope,
    ):
        connection = VerifiedConnection(
            runtime.endpoint.connect(timeout=3),
            expected=ClientHello(product_version="test", storage_identity=runtime.endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
        human_projection = (
            OperationFrontendProjection.CLI if projection is OperationFrontendProjection.EXTERNAL_CLIENT else projection
        )
        frontend = FrontendClient(connection, profile_id=runtime.profile_id, frontend=human_projection)
        scope.callback(frontend.close)
        signed_in = frontend.login_password(bytearray(PROFILE_INPUT, "utf-8"))
        assert signed_in.status.denial is None, signed_in
        client = runtime.connect_service()
        assert client.connected is not None
        assert isinstance(
            frontend.service_admission(client.connected.connection_id, client.service_id), ServiceConnected
        )
        assert client.claim() is not None
        service = AgentService(
            client=client,
            storage_root=runtime.root,
            gateway_bearer=bytearray(b"g" * 64),
            emit=lambda _event: None,
        )
        scope.callback(service.close)
        bearer = b"a" * 64
        admin = AdminServer(service, bearer=bytearray(bearer))
        scope.callback(admin.close)
        changed = _admin(
            admin,
            bearer,
            "model_role_set",
            role="text_extraction",
            provider="local_api",
            model="synthetic-text:1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        assert changed["unreadable"] is False, changed
        revision = changed["revision"]
        assert revision != ABSENT_SECURE_OBJECT_REVISION_ID

        # A newly composed reader must obtain the committed record, not admin state.
        read = SecureModelRoleSelectionsStore(client=client).read()
        assert isinstance(read, StoredModelRoleSelections), read
        assert read.revision == revision
        assert [(entry.role.value, entry.lane, entry.model) for entry in read.record.selections] == [
            ("text_extraction", "local_api", "synthetic-text:1"),
        ]
        relay = ModelRunRelay(client=client, runs=service.model_runs)
        scope.callback(relay.close)
        scope.callback(client.subscribe_model_runs(relay.announce))

        def lookup(role: str | None) -> ModelRunOutcome:
            request = WorkerModelRun(request_id=uuid4(), permit_id=uuid4(), command_id=uuid4(), role=role)
            outcome, text = runtime.profiles._relay_model_run(runtime.profile_id, request, bytearray())
            assert text == bytearray()
            return outcome

        lane = lookup("text_extraction").lane
        assert lane is not None
        assert (lane.provider_id, lane.transport, lane.model) == ("local", "api", "synthetic-text:1")
        states = lookup(None).selections
        assert states is not None
        selected = next(state for state in states if state.role == "text_extraction")
        assert selected.selected == ModelRunSelectedModel(lane_id="local_api", model="synthetic-text:1")
        assert selected.lane == lane
        assert all(
            state.refusal is ModelRunRefusalCode.NO_SELECTION for state in states if state.role != "text_extraction"
        )
        if projection is OperationFrontendProjection.CLI:
            completion = run_registered_operation(
                frontend,
                LocalReaderReportRequest(),
                definition_id=LOCAL_READER_REPORT_OPERATION_DEFINITION_ID,
                subject_ref=LOCAL_READER_OPERATION_SUBJECT,
                result_type=LocalReaderReportPublicResultV1,
                request_version=1,
                result_version=1,
                timeout=20,
            )
            report = completion.projection
        elif projection is OperationFrontendProjection.TUI:
            report = asyncio.run(_tui_report(frontend))
        else:
            external_connection = VerifiedConnection(
                runtime.endpoint.connect(timeout=3),
                expected=ClientHello(product_version="test", storage_identity=runtime.endpoint.storage_identity),
                deadline=time.monotonic() + 3,
            )
            external = FrontendClient(
                external_connection,
                profile_id=runtime.profile_id,
                frontend=projection,
                scope=AccessScope(
                    operations=frozenset({LOCAL_READER_REPORT_OPERATION_DEFINITION_ID}),
                    actions=frozenset(AccessAction) - {AccessAction.COMMIT},
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                    allow_changes_records=False,
                    allow_network=False,
                ),
            )
            scope.callback(external.close)
            assert frontend.attendance_inventory().candidates == ()
            ask = external.request_attendance()
            assert isinstance(ask, AttendancePending), ask
            assert frontend.decide_attendance(ask.attendance_id, approve=True).approved
            attended = external.attendance_status(ask.attendance_id)
            assert isinstance(attended, ProfileStatus), attended
            assert attended.status.denial is None, attended
            assert external.session_id != frontend.session_id
            adapter = RuntimeMcpAdapter(profile_id=runtime.profile_id, client=external)
            scope.callback(lambda: asyncio.run(adapter.close()))
            report = asyncio.run(_mcp_report(adapter, external))
        model = next(row for row in report.models if row.role.value == "text_extraction")
        assert model.selected is True
        assert model.model == "synthetic-text:1"
        assert _admin(admin, bearer, "model_roles")["revision"] == revision
        reread = SecureModelRoleSelectionsStore(client=client).read()
        assert reread == read
