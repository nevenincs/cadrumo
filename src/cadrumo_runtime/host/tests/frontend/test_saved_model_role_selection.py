"""Desktop administration persists the choice the shared runtime model relay reads.

This joins the authenticated desktop admin protocol, agent service, encrypted
runtime custody and both production relays. Installed-image verification and
the upstream agent catalogue are explicit test ports. Frontend UI submission
and native desktop invocation are outside this boundary.
"""

from __future__ import annotations

import json
import socket
import struct
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from cadrumo.adapters.persistence.storage.secure_object_namespaces import (
    EXTENSION_SETTINGS_NAMESPACE,
    MODEL_ROLE_SELECTIONS_NAMESPACE,
)
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
from cadrumo_client.contracts.extension_records import ExtensionRecordCapability
from cadrumo_client.contracts.model_runs import (
    MODEL_RUN_LANE_ID_PATTERN,
    ModelRunOutcome,
    ModelRunRefusalCode,
    ModelRunSelectedModel,
)
from cadrumo_client.contracts.service_access import ServiceConnected

from ....contracts.worker_authorization import WorkerModelRun
from ..test_service_records import service_record_runtime

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


def test_authenticated_desktop_choice_survives_new_store_and_runtime_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def declared_catalog(self: AgentProviderCatalogSource) -> ProviderCatalog:
        return synthetic_catalog()

    monkeypatch.setattr(AgentProviderCatalogSource, "catalog", declared_catalog)
    capabilities = tuple(_capability(name) for name in (MODEL_ROLE_SELECTIONS_CAPABILITY, PROVIDER_RECORD_CAPABILITY))
    with (
        service_record_runtime(tmp_path, record_capabilities=capabilities, model_runs=True) as runtime,
        ExitStack() as scope,
    ):
        client = runtime.connect_service()
        assert isinstance(runtime.admit(client), ServiceConnected)
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
        assert _admin(admin, bearer, "model_roles")["revision"] == revision
        reread = SecureModelRoleSelectionsStore(client=client).read()
        assert reread == read
