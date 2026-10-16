"""Real worker custody under explicitly controlled login/service verification ports."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.secure_object_namespaces import EXTENSION_SETTINGS_NAMESPACE
from cadrumo.application.user_profile.access_contracts import AccessScope
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.extension_records import (
    ExtensionRecordCapability,
    ExtensionRecordRefusal,
    ExtensionRecordReply,
    ExtensionRecordRequest,
)
from cadrumo_client.contracts.profile_access import ProfileStatus, SessionRequest, SessionsLocked
from cadrumo_client.contracts.service_access import (
    InstalledServiceDescriptor,
    ServiceAdmission,
    ServiceConnected,
    VerifiedServicePeer,
)
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_client.transport.transport_cleanup import TransportCleanup
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, NativeRuntimeFixtureOwner, owner_id, worker_profiles
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation, connect, login

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows transport and workers"),
    pytest.mark.usefixtures("authority_operation"),
]

RECORD_CAPABILITY = "synthetic_records"
SERVICE_ID = "synthetic-record-service"


class ControlledServiceVerifier:
    """Admit only connections deliberately selected by this serialized fixture.

    Native transport still verifies its peer. Installed image/module verification
    is controlled here and is therefore not native installed-service evidence.
    """

    def __init__(self) -> None:
        self.accept_next = False
        self.connections: set[UUID] = set()

    def verify_service(
        self, context: ConnectionContext, channel: ByteChannel, descriptor: InstalledServiceDescriptor
    ) -> VerifiedServicePeer | None:
        if self.accept_next:
            self.connections.add(context.connection_id)
            self.accept_next = False
        if context.connection_id not in self.connections:
            return None
        assert context.peer == channel.peer
        assert context.peer.process_id is not None
        return VerifiedServicePeer(
            service_id=descriptor.service_id,
            descriptor_digest=descriptor.descriptor_digest,
            process_id=context.peer.process_id,
            process_incarnation="explicitly-controlled-fixture-incarnation",
            image_path=descriptor.launch_image,
            image_digest=descriptor.image_digest,
            connection_id=context.connection_id,
            runtime_boot_id=context.runtime_boot_id,
            image_identity="explicitly-controlled-fixture-image",
        )

    def recheck_service(self, context: ConnectionContext, channel: ByteChannel, peer: VerifiedServicePeer) -> bool:
        assert context.peer == channel.peer
        return context.connection_id in self.connections and context.connection_id == peer.connection_id

    def installed_parent_image_matches(self, image_path: str, descriptor_path: str, image_digest: str) -> bool:
        return False

    def verify_descendant(
        self, context: ConnectionContext, channel: ByteChannel, service_peer: VerifiedServicePeer, group_id: UUID
    ) -> bool:
        return False


@dataclass
class ServiceRecordRuntime:
    """Public transport fixture available to higher-level service consumer tests."""

    root: Path
    profile_id: UUID
    other_profile_id: UUID
    endpoint: WindowsEndpoint
    human: VerifiedConnection
    person_session_id: UUID
    verifier: ControlledServiceVerifier
    clients: list[VerifiedConnection] = field(default_factory=list)

    def connect_service(self, *, profile_id: UUID | None = None) -> InstalledServiceClient:
        connection = connect(self.endpoint)
        self.clients.append(connection)
        self.verifier.accept_next = True
        service = InstalledServiceClient(connection, profile_id=profile_id or self.profile_id, service_id=SERVICE_ID)
        assert service.claim() is None
        assert service.connected is not None and service.connected.lease is None
        return service

    def admit(self, service: InstalledServiceClient):
        assert service.connected is not None
        return self.human.service_access(
            ServiceAdmission(
                request_id=uuid4(),
                profile_id=self.profile_id,
                session_id=self.person_session_id,
                recipient_connection_id=service.connected.connection_id,
                service_id=SERVICE_ID,
            ),
            deadline=time.monotonic() + 10,
        )


def _retained_connections_for_cleanup(
    fixture: ServiceRecordRuntime | None, human: VerifiedConnection | None
) -> tuple[VerifiedConnection, ...]:
    """Collect completed connections in close order, including partial setup."""
    clients = () if fixture is None else tuple(fixture.clients)
    if human is not None:
        clients += (human,)
    return clients


@contextmanager
def service_record_runtime(
    tmp_path: Path, *, record_capabilities: tuple[ExtensionRecordCapability, ...] | None = None
) -> Generator[ServiceRecordRuntime]:
    """Start real encrypted profiles and workers with two controlled authority ports."""
    with worker_profiles(tmp_path) as (root, targets):
        endpoint = WindowsEndpoint(storage_root=root)
        installation(storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity)
        namespace = EXTENSION_SETTINGS_NAMESPACE
        policy = ExtensionRecordCapability(
            capability=RECORD_CAPABILITY,
            namespace=namespace.namespace,
            schema_version=namespace.schema_version,
            classification=namespace.sensitivity,
            key_pattern=r"synthetic-[a-z]+",
            actions=frozenset({"read", "write", "delete", "generation"}),
        )
        descriptor = InstalledServiceDescriptor(
            service_id=SERVICE_ID,
            launch_image=sys.executable,
            launch_module="synthetic.service",
            image_digest="1" * 64,
            descriptor_digest="2" * 64,
            record_capabilities=(policy,) if record_capabilities is None else record_capabilities,
            operation_scope=AccessScope(
                operations=frozenset(),
                actions=frozenset(),
                disclosures=frozenset(),
                periods=None,
                allow_period_independent=True,
                allow_delegation=False,
            ),
        )
        stop, boot, native, verifier = Event(), uuid4(), MemoryNativePort(), ControlledServiceVerifier()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id()),
            secret_store=lambda: native,
            service_descriptors=(descriptor,),
            service_verifier=verifier,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        human: VerifiedConnection | None = None
        fixture: ServiceRecordRuntime | None = None
        owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
        pool = ThreadPoolExecutor(max_workers=1)
        owner.executor = pool
        owner.server = server
        owner.running = pool.submit(server.serve)
        try:
            assert server.ready.wait(3)
            human = connect(endpoint)
            profile = targets[0][0].binding.profile_id
            admitted = login(human, profile, "password", PROFILE_INPUT.encode())
            assert isinstance(admitted, ProfileStatus), admitted
            assert admitted.status.denial is None, admitted
            assert admitted.status.session_id is not None
            fixture = ServiceRecordRuntime(
                root,
                profile,
                targets[1][0].binding.profile_id,
                endpoint,
                human,
                admitted.status.session_id,
                verifier,
            )
            yield fixture
        finally:
            clients = _retained_connections_for_cleanup(fixture, human)
            asyncio.run(
                close_async_resources(
                    *(TransportCleanup(client) for client in clients),
                    owner,
                    task_name="service-record-runtime-close",
                    primary_error=sys.exception(),
                )
            )


def test_real_service_record_cas_generation_delete_and_payload_wipe(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        approved = runtime.admit(service)
        assert isinstance(approved, ServiceConnected), approved
        lease = service.claim()
        assert lease is not None and lease.parent_session_id == runtime.person_session_id
        assert lease.profile_id == runtime.profile_id

        absent, material = service.record_read(RECORD_CAPABILITY, "synthetic-record")
        assert absent.state == "absent" and material == bytearray()
        initial = service.observe_generation(RECORD_CAPABILITY)
        assert initial.state == "generation" and initial.records_generation is not None

        payload = bytearray(b"synthetic opaque credential payload")
        written = service.record_write(
            RECORD_CAPABILITY, "synthetic-record", payload, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        assert payload == bytearray(len(payload))
        assert written.state == "written" and written.revision is not None, written
        present, material = service.record_read(RECORD_CAPABILITY, "synthetic-record")
        try:
            assert present.state == "present" and present.revision == written.revision
            assert material == b"synthetic opaque credential payload"
        finally:
            material[:] = bytes(len(material))
        populated = service.observe_generation(RECORD_CAPABILITY)
        assert populated.records_generation != initial.records_generation

        stale = bytearray(b"stale synthetic update")
        conflict = service.record_write(
            RECORD_CAPABILITY, "synthetic-record", stale, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        assert stale == bytearray(len(stale))
        assert conflict.state == "refused" and conflict.refusal is ExtensionRecordRefusal.REVISION_CONFLICT
        assert service.observe_generation(RECORD_CAPABILITY).records_generation == populated.records_generation

        replacement = bytearray(b"updated synthetic payload")
        updated = service.record_write(
            RECORD_CAPABILITY, "synthetic-record", replacement, expected_revision=written.revision
        )
        assert replacement == bytearray(len(replacement))
        assert updated.state == "written"
        assert updated.revision is not None and updated.revision != written.revision
        stale_delete = service.record_delete(RECORD_CAPABILITY, "synthetic-record", expected_revision=written.revision)
        assert stale_delete.refusal is ExtensionRecordRefusal.REVISION_CONFLICT
        deleted = service.record_delete(RECORD_CAPABILITY, "synthetic-record", expected_revision=updated.revision)
        assert deleted.state == "deleted"
        absent, material = service.record_read(RECORD_CAPABILITY, "synthetic-record")
        assert absent.state == "absent" and material == bytearray()
        assert service.observe_generation(RECORD_CAPABILITY).records_generation == initial.records_generation


def test_service_records_refuse_wrong_profile_capability_and_retired_person(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        unverified = connect(runtime.endpoint)
        runtime.clients.append(unverified)
        with pytest.raises(RefusalError) as refused:
            InstalledServiceClient(unverified, profile_id=runtime.profile_id, service_id=SERVICE_ID).claim()
        assert refused.value.reason is RefusalCode.CONNECTION_CLOSED
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        lease = service.claim()
        assert lease is not None

        def read(*, profile_id: UUID, capability: str) -> ExtensionRecordReply:
            reply, material = service.connection.extension_record(
                ExtensionRecordRequest(
                    action="extension_record_read",
                    request_id=uuid4(),
                    profile_id=profile_id,
                    session_id=lease.session_id,
                    lease_id=lease.lease_id,
                    capability=capability,
                    object_key="synthetic-record",
                ),
                deadline=time.monotonic() + 10,
            )
            assert material == bytearray()
            assert isinstance(reply, ExtensionRecordReply)
            assert reply.state == "refused"
            return reply

        wrong_profile = read(profile_id=runtime.other_profile_id, capability=RECORD_CAPABILITY)
        assert wrong_profile.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        wrong_capability = read(profile_id=runtime.profile_id, capability="unregistered")
        assert wrong_capability.refusal is ExtensionRecordRefusal.CAPABILITY_DENIED
        locked = runtime.human.session(
            SessionRequest(
                action="session_lock",
                request_id=uuid4(),
                profile_id=runtime.profile_id,
                session_id=runtime.person_session_id,
            ),
            deadline=time.monotonic() + 10,
        )
        assert isinstance(locked, SessionsLocked)
        assert runtime.person_session_id in locked.session_ids
        retired = read(profile_id=runtime.profile_id, capability=RECORD_CAPABILITY)
        assert retired.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
