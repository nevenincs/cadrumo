"""Authenticated desktop administration persists the model used by per-role runtime lookups."""

from __future__ import annotations

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
    LOCAL_MODEL_LIST_NAMESPACE,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_agent_service.adapters.agent_provider_catalog import AgentProviderCatalogSource
from cadrumo_agent_service.admin import AdminServer
from cadrumo_agent_service.host.model_run_relay import ModelRunRelay
from cadrumo_agent_service.providers.application.ports import StoredLocalModelList
from cadrumo_agent_service.providers.application.tests.synthetic_catalog import synthetic_document
from cadrumo_agent_service.providers.domain.catalog import ProviderCatalog, parse_provider_catalog
from cadrumo_agent_service.providers.domain.record import ListedModel
from cadrumo_agent_service.providers.persistence.store import (
    LOCAL_MODEL_LIST_CAPABILITY,
    PROVIDER_RECORD_CAPABILITY,
    SecureLocalModelListStore,
)
from cadrumo_agent_service.service import AgentService
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.extension_records import ExtensionRecordCapability
from cadrumo_client.contracts.model_runs import (
    MODEL_RUN_LANE_ID_PATTERN,
    ModelRunOutcome,
    ModelRunRefusalCode,
)
from cadrumo_client.contracts.service_access import ServiceConnected
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.adapters.tests.profile_worker_support import PROFILE_INPUT
from cadrumo_runtime.contracts.worker_authorization import WorkerModelRun
from cadrumo_runtime.host.tests.test_service_records import service_record_runtime

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]


def _capability(name: str) -> ExtensionRecordCapability:
    selections = name == LOCAL_MODEL_LIST_CAPABILITY
    namespace = LOCAL_MODEL_LIST_NAMESPACE if selections else EXTENSION_SETTINGS_NAMESPACE
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


def _unrecommended_catalog() -> ProviderCatalog:
    """The synthetic catalogue with no recommended local model, so the local list holds only what the person adds."""
    document = json.loads(synthetic_document())
    for lane in document["providers"]:
        if lane["id"] == "local_api":
            lane["recommended"] = {}
    return parse_provider_catalog(json.dumps(document))


@pytest.mark.parametrize(
    "projection",
    [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI],
)
def test_authenticated_desktop_model_list_survives_new_store_and_runtime_lookup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    projection: OperationFrontendProjection,
) -> None:
    def declared_catalog(self: AgentProviderCatalogSource) -> ProviderCatalog:
        return _unrecommended_catalog()

    monkeypatch.setattr(AgentProviderCatalogSource, "catalog", declared_catalog)
    capabilities = tuple(_capability(name) for name in (LOCAL_MODEL_LIST_CAPABILITY, PROVIDER_RECORD_CAPABILITY))
    with (
        service_record_runtime(tmp_path, record_capabilities=capabilities, model_runs=True) as runtime,
        ExitStack() as scope,
    ):
        connection = VerifiedConnection(
            runtime.endpoint.connect(timeout=3),
            expected=ClientHello(product_version="test", storage_identity=runtime.endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
        frontend = FrontendClient(connection, profile_id=runtime.profile_id, frontend=projection)
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
            "local_model_add",
            provider="local_api",
            model="synthetic-text:1",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        assert changed["unreadable"] is False, changed
        chosen = _admin(
            admin,
            bearer,
            "reading_model_choose",
            provider="local_api",
            model="synthetic-text:1",
            expected_revision=changed["revision"],
        )
        assert chosen["reading"] == {"lane": "local_api", "model": "synthetic-text:1"}, chosen
        revision = chosen["revision"]
        assert revision not in {ABSENT_SECURE_OBJECT_REVISION_ID, changed["revision"]}

        # A newly composed reader must obtain the committed record, not admin state.
        read = SecureLocalModelListStore(client=client).read()
        assert isinstance(read, StoredLocalModelList), read
        assert read.revision == revision
        assert read.record.models == (ListedModel(lane="local_api", model="synthetic-text:1"),)
        assert read.record.reading == ListedModel(lane="local_api", model="synthetic-text:1")
        relay = ModelRunRelay(client=client, runs=service.model_runs)
        scope.callback(relay.close)
        scope.callback(client.subscribe_model_runs(relay.announce))

        def lookup(role: str) -> ModelRunOutcome:
            request = WorkerModelRun(request_id=uuid4(), permit_id=uuid4(), command_id=uuid4(), role=role)
            outcome, text = runtime.profiles._relay_model_run(runtime.profile_id, request, bytearray())
            assert text == bytearray()
            return outcome

        lane = lookup("text_extraction").lane
        assert lane is not None
        assert (lane.provider_id, lane.transport, lane.model) == ("local", "api", "synthetic-text:1")
        for role in ("text_extraction", "column_role_mapping", "supply_nature_proposal"):
            outcome = lookup(role)
            assert outcome.lane == lane
            assert outcome.refusal is None
        # Nothing states the added model reads images, so the image role refuses.
        vision = lookup("vision_transcription")
        assert vision.lane is None
        assert vision.refusal is ModelRunRefusalCode.MODEL_CANNOT_READ_IMAGES
        assert _admin(admin, bearer, "local_models")["revision"] == revision
        reread = SecureLocalModelListStore(client=client).read()
        assert reread == read
