"""Real worker custody under explicitly controlled login/service verification ports."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, get_ident
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.secure_object_namespaces import EXTENSION_SETTINGS_NAMESPACE
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.core.async_cleanup import close_async_resources
from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import AccessScope
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.extension_records import (
    ExtensionRecordCapability,
    ExtensionRecordRefusal,
    ExtensionRecordReply,
    ExtensionRecordRequest,
)
from cadrumo_client.contracts.profile_access import ProfileStatus, SecretReady, SessionRequest, SessionsLocked
from cadrumo_client.contracts.service_access import (
    InstalledServiceDescriptor,
    ServiceAdmission,
    ServiceAdmissionPending,
    ServiceAdmissionStatusQuery,
    ServiceCapability,
    ServiceConnected,
    VerifiedServicePeer,
)
from cadrumo_client.contracts.session_events import ServiceAdmissionChanged
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_client.transport.transport_cleanup import TransportCleanup
from cadrumo_client.transport.windows import WindowsEndpoint

from ...adapters.tests.profile_worker_support import PROFILE_INPUT, NativeRuntimeFixtureOwner, owner_id, worker_profiles
from ...adapters.tests.retained_server import RetainedRuntimeTransportServer
from .. import profile_connection_extension_records as extension_records
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
OTHER_SERVICE_ID = "synthetic-other-service"


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
    profiles: RuntimeProfileConnections
    clients: list[VerifiedConnection] = field(default_factory=list)

    def connect_service(
        self, *, profile_id: UUID | None = None, service_id: str = SERVICE_ID
    ) -> InstalledServiceClient:
        connection = connect(self.endpoint)
        self.clients.append(connection)
        self.verifier.accept_next = True
        service = InstalledServiceClient(connection, profile_id=profile_id or self.profile_id, service_id=service_id)
        assert service.claim() is None
        assert service.connected is not None and service.connected.lease is None
        return service

    def admit(self, service: InstalledServiceClient):
        assert service.connected is not None
        person = FrontendClient(self.human, profile_id=self.profile_id, frontend=OperationFrontendProjection.CLI)
        person._session_id = self.person_session_id
        return person.service_admission(service.connected.connection_id, service.service_id)


def _retained_connections_for_cleanup(
    fixture: ServiceRecordRuntime | None, human: VerifiedConnection | None
) -> tuple[VerifiedConnection, ...]:
    """Collect completed connections in close order, including partial setup."""
    clients = () if fixture is None else tuple(fixture.clients)
    if human is not None:
        clients += (human,)
    return clients


def _descriptor(
    service_id: str,
    record_capabilities: tuple[ExtensionRecordCapability, ...],
    *,
    model_runs: bool,
    digest: str,
) -> InstalledServiceDescriptor:
    return InstalledServiceDescriptor(
        service_id=service_id,
        launch_image=sys.executable,
        launch_module="synthetic.service",
        image_digest="1" * 64,
        descriptor_digest=digest * 64,
        record_capabilities=record_capabilities,
        operation_scope=AccessScope(
            operations=frozenset(),
            actions=frozenset(),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        ),
        service_capabilities=(ServiceCapability.MODEL_RUN,) if model_runs else (),
    )


@contextmanager
def service_record_runtime(
    tmp_path: Path,
    *,
    record_capabilities: tuple[ExtensionRecordCapability, ...] | None = None,
    model_runs: bool = False,
    other_service_model_runs: bool | None = None,
) -> Generator[ServiceRecordRuntime]:
    """Start real encrypted profiles and workers with two controlled authority ports.

    ``model_runs`` says whether the installed descriptor of :data:`SERVICE_ID`
    admits model runs. ``other_service_model_runs``, when given, installs a
    second descriptor, :data:`OTHER_SERVICE_ID`, that does or does not.
    """
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
        descriptors = [
            _descriptor(
                SERVICE_ID,
                (policy,) if record_capabilities is None else record_capabilities,
                model_runs=model_runs,
                digest="2",
            )
        ]
        if other_service_model_runs is not None:
            descriptors.append(_descriptor(OTHER_SERVICE_ID, (), model_runs=other_service_model_runs, digest="3"))
        stop, boot, native, verifier = Event(), uuid4(), MemoryNativePort(), ControlledServiceVerifier()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id()),
            secret_store=lambda: native,
            service_descriptors=tuple(descriptors),
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
                profiles,
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


def test_service_records_recheck_peer_before_access_or_accepting_secret_input(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        assert service.claim() is not None
        assert service.connected is not None
        runtime.verifier.connections.remove(service.connected.connection_id)

        read, material = service.record_read(RECORD_CAPABILITY, "synthetic-record")
        assert read.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        assert material == bytearray()
        generation = service.observe_generation(RECORD_CAPABILITY)
        assert generation.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        deleted = service.record_delete(
            RECORD_CAPABILITY, "synthetic-record", expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        assert deleted.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        payload = bytearray(b"synthetic secret never admitted")
        written = service.record_write(
            RECORD_CAPABILITY, "synthetic-record", payload, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        assert written.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        assert payload == bytearray(len(payload))


@contextmanager
def _paused_service_recheck(
    runtime: ServiceRecordRuntime, monkeypatch: pytest.MonkeyPatch, *, check_number: int = 1
) -> Generator[tuple[Event, Event]]:
    entered, release = Event(), Event()
    original = runtime.verifier.recheck_service
    checks = 0

    def paused(context: ConnectionContext, channel: ByteChannel, peer: VerifiedServicePeer) -> bool:
        nonlocal checks
        verified = original(context, channel, peer)
        checks += 1
        if checks == check_number:
            entered.set()
            assert release.wait(20), "test did not release native service verification"
        return verified

    with monkeypatch.context() as patch:
        patch.setattr(runtime.verifier, "recheck_service", paused)
        try:
            yield entered, release
        finally:
            release.set()


@pytest.mark.parametrize("cancel", [False, True])
def test_pending_service_admission_frees_the_person_slot_and_cannot_publish_after_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel: bool
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert service.connected is not None
        finished = Event()
        unsubscribe = runtime.human.subscribe_session_events(
            lambda event: finished.set() if isinstance(event, ServiceAdmissionChanged) else None
        )
        try:
            with _paused_service_recheck(runtime, monkeypatch) as (entered, release):
                pending = runtime.human.service_access(
                    ServiceAdmission(
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        session_id=runtime.person_session_id,
                        recipient_connection_id=service.connected.connection_id,
                        service_id=service.service_id,
                    ),
                    deadline=time.monotonic() + 30,
                )
                assert isinstance(pending, ServiceAdmissionPending)
                assert entered.wait(20), "verification did not reach its controlled barrier"
                # This is the same native person connection, not a second
                # frontend that happens to hold a sibling human session.
                status = runtime.human.session(
                    SessionRequest(
                        action="session_status",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        session_id=runtime.person_session_id,
                    ),
                    deadline=time.monotonic() + 30,
                )
                assert isinstance(status, ProfileStatus) and status.status.denial is None
                query = ServiceAdmissionStatusQuery(
                    action="service_admission_cancel" if cancel else "service_admission_status",
                    request_id=uuid4(),
                    profile_id=runtime.profile_id,
                    session_id=runtime.person_session_id,
                    recipient_connection_id=service.connected.connection_id,
                    service_id=service.service_id,
                    admission_id=pending.admission_id,
                )
                waiting = runtime.human.service_access(query, deadline=time.monotonic() + 30)
                assert isinstance(waiting, ServiceAdmissionPending) and waiting.cancelled is cancel
                release.set()
                assert finished.wait(30), "verification completion did not cue its exact holder"
            if cancel:
                assert service.claim() is None
            else:
                answer = runtime.human.service_access(
                    query.model_copy(update={"request_id": uuid4()}), deadline=time.monotonic() + 30
                )
                assert isinstance(answer, ServiceConnected) and answer.lease is not None
                assert service.claim() == answer.lease
                stored = service.record_write(
                    RECORD_CAPABILITY,
                    "synthetic-record",
                    bytearray(b"synthetic typed profile projection"),
                    expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
                )
                assert stored.state == "written"
                present, material = service.record_read(RECORD_CAPABILITY, "synthetic-record")
                try:
                    assert present.state == "present" and material == b"synthetic typed profile projection"
                finally:
                    material[:] = bytes(len(material))
        finally:
            unsubscribe()


@pytest.mark.parametrize(
    ("action", "check_number"), [("read", 1), ("generation", 1), ("delete", 1), ("write", 1), ("write", 2)]
)
def test_service_record_verification_allows_profile_status_and_lock_without_stale_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str, check_number: int
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        assert service.claim() is not None
        payload = bytearray(b"synthetic blocked write")

        def request_record() -> tuple[ExtensionRecordReply, bytearray]:
            if action == "read":
                return service.record_read(RECORD_CAPABILITY, "synthetic-record")
            if action == "generation":
                return service.observe_generation(RECORD_CAPABILITY), bytearray()
            if action == "delete":
                return service.record_delete(
                    RECORD_CAPABILITY, "synthetic-record", expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
                ), bytearray()
            return service.record_write(
                RECORD_CAPABILITY, "synthetic-record", payload, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
            ), bytearray()

        host = runtime.profiles._profiles[runtime.profile_id]
        original_access = host.owner.extension_record
        accesses: list[UUID] = []

        def record_access(request, material):
            accesses.append(request.request_id)
            return original_access(request, material)

        monkeypatch.setattr(host.owner, "extension_record", record_access)
        with (
            _paused_service_recheck(runtime, monkeypatch, check_number=check_number) as (entered, release),
            ThreadPoolExecutor(max_workers=1) as pool,
        ):
            pending = pool.submit(request_record)
            try:
                assert entered.wait(5), "record request did not reach native verification"
                status = runtime.human.session(
                    SessionRequest(
                        action="session_status",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        session_id=runtime.person_session_id,
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(status, ProfileStatus) and status.status.denial is None
                locked = runtime.human.session(
                    SessionRequest(
                        action="session_lock",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        session_id=runtime.person_session_id,
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(locked, SessionsLocked)
                assert runtime.person_session_id in locked.session_ids
            finally:
                release.set()
            reply, material = pending.result(timeout=10)
        assert reply.refusal is ExtensionRecordRefusal.LEASE_INACTIVE
        assert material == bytearray()
        assert accesses == []
        if action == "write":
            assert payload == bytearray(len(payload))


@pytest.mark.parametrize("retirement", ["holder_lock", "recipient_disconnect", "recipient_disconnecting"])
def test_service_admission_verification_allows_profile_work_and_refuses_retired_connections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retirement: str
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert service.connected is not None
        recipient_id = service.connected.connection_id
        recipient = runtime.profiles._connections[recipient_id]
        retained = runtime.profiles._services[recipient_id]
        host = runtime.profiles._profiles[runtime.profile_id]
        retiring, finish_cleanup = Event(), Event()
        original_retire = host.approvals.retire_connection

        def paused_retirement(connection_id: UUID) -> None:
            original_retire(connection_id)
            if connection_id == recipient_id:
                retiring.set()
                assert finish_cleanup.wait(20), "test did not release disconnect cleanup"

        if retirement == "recipient_disconnecting":
            monkeypatch.setattr(host.approvals, "retire_connection", paused_retirement)
        holder = next(
            item for item in runtime.profiles._connections.values() if item.session_id == runtime.person_session_id
        )
        admission = ServiceAdmission(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=runtime.person_session_id,
            recipient_connection_id=recipient_id,
            service_id=SERVICE_ID,
        )
        with (
            _paused_service_recheck(runtime, monkeypatch) as (entered, release),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            # Invoke the owning admission handler so the human's transport can
            # exercise another real profile request while verification waits.
            pending = pool.submit(runtime.profiles._admit_service, holder.context, admission)
            disconnect = None
            try:
                assert entered.wait(5), "admission did not reach native verification"
                status = runtime.human.session(
                    SessionRequest(
                        action="session_status",
                        request_id=uuid4(),
                        profile_id=runtime.profile_id,
                        session_id=runtime.person_session_id,
                    ),
                    deadline=time.monotonic() + 3,
                )
                assert isinstance(status, ProfileStatus) and status.status.denial is None
                if retirement == "holder_lock":
                    locked = runtime.human.session(
                        SessionRequest(
                            action="session_lock",
                            request_id=uuid4(),
                            profile_id=runtime.profile_id,
                            session_id=runtime.person_session_id,
                        ),
                        deadline=time.monotonic() + 5,
                    )
                    assert isinstance(locked, SessionsLocked)
                elif retirement == "recipient_disconnect":
                    runtime.profiles.disconnect(recipient.context)
                else:
                    disconnect = pool.submit(runtime.profiles.disconnect, recipient.context)
                    assert retiring.wait(5), "disconnect did not reach post-authority cleanup"
                    assert runtime.profiles._connections.get(recipient_id) is recipient
                    # Registry membership alone cannot resurrect a recipient whose
                    # authority has ended but whose cleanup has not returned.
                    with pytest.raises(ProfileAccessRefusedError) as ended:
                        host.authority.attend(
                            connection_id=holder.context.connection_id,
                            parent_session_id=runtime.person_session_id,
                            recipient_connection_id=recipient_id,
                            scope=retained.descriptor.operation_scope,
                        )
                    assert ended.value.reason is AccessDenialCode.CONNECTION_MISMATCH
                    release.set()
                    refused = pending.result(timeout=10)
                    assert isinstance(refused, AccessDenied)
                    assert retained.lease is None
            finally:
                release.set()
                finish_cleanup.set()
            refused = pending.result(timeout=10)
            if disconnect is not None:
                disconnect.result(timeout=10)
        assert isinstance(refused, AccessDenied)
        assert refused.code is (
            AccessDenialCode.HUMAN_AUTHORITY_REQUIRED
            if retirement == "holder_lock"
            else AccessDenialCode.CONNECTION_MISMATCH
        )
        assert retained.lease is None
        assert recipient.session_id is None


def test_service_refresh_tolerates_lease_retirement_before_profile_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        lease = service.claim()
        assert lease is not None
        assert service.connected is not None

        service_connection_id = service.connected.connection_id
        retained = runtime.profiles._services[service_connection_id]
        host = runtime.profiles._profiles[runtime.profile_id]
        profile_guard = host.guard

        class RetireBeforeRequestGuard:
            target_thread: int | None = None

            def __enter__(self):
                profile_guard.acquire()
                try:
                    if self.target_thread == get_ident():
                        with runtime.profiles._guard:
                            assert retained.lease == lease
                            retained.lease = None
                        self.target_thread = None
                    return self
                except BaseException:
                    profile_guard.release()
                    raise

            def __exit__(self, *_exc_info: object) -> None:
                profile_guard.release()

        request_guard = RetireBeforeRequestGuard()
        original_recheck = runtime.verifier.recheck_service

        def arm_request_guard(context: ConnectionContext, channel: ByteChannel, peer: VerifiedServicePeer) -> bool:
            proven = original_recheck(context, channel, peer)
            if context.connection_id == service_connection_id:
                request_guard.target_thread = get_ident()
            return proven

        with monkeypatch.context() as patch:
            patch.setattr(host, "guard", request_guard)
            patch.setattr(runtime.verifier, "recheck_service", arm_request_guard)
            assert service.claim() is None

        assert service.connected is not None and service.connected.lease is None
        assert retained.lease is None


def test_service_record_reply_is_not_bounded_by_the_client_input_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        assert service.claim() is not None
        stored = bytearray(b"synthetic payload read after a long queue")
        written = service.record_write(
            RECORD_CAPABILITY, "synthetic-record", stored, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
        )
        assert written.state == "written"

        # Serving a read always outlasts a client input window this short, as waiting on the guards does a long one.
        with monkeypatch.context() as patch:
            patch.setattr(extension_records, "_CLIENT_INPUT_SECONDS", 0.001)
            present, material = service.record_read(RECORD_CAPABILITY, "synthetic-record")
        try:
            assert present.state == "present" and present.revision == written.revision
            assert material == b"synthetic payload read after a long queue"
        finally:
            material[:] = bytes(len(material))

        # The connection survived and serves the next request.
        generation = service.observe_generation(RECORD_CAPABILITY)
        assert generation.state == "generation" and generation.records_generation is not None
        assert not service.connection.closed


def test_service_record_write_input_is_bounded_and_waited_for_outside_the_profile_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        lease = service.claim()
        assert lease is not None
        host = runtime.profiles._profiles[runtime.profile_id]
        request = ExtensionRecordRequest(
            action="extension_record_write",
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=lease.session_id,
            lease_id=lease.lease_id,
            capability=RECORD_CAPABILITY,
            object_key="synthetic-record",
            expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID,
            byte_count=16,
        )

        with monkeypatch.context() as patch:
            patch.setattr(extension_records, "_CLIENT_INPUT_SECONDS", 5.0)
            with service.connection.held_exchange(request, request.request_id, deadline=time.monotonic() + 30) as held:
                assert isinstance(held.reply().root, SecretReady)
                waiting_since = time.monotonic()
                # A service that withholds its secret must not keep the profile fenced meanwhile.
                assert host.guard.acquire(timeout=2)
                host.guard.release()
                # The runtime, not this client, ends the wait: the connection closes when the window does.
                with pytest.raises(RefusalError) as closed:
                    held.reply()
        assert closed.value.reason is RefusalCode.CONNECTION_CLOSED
        assert time.monotonic() - waiting_since < 20


def test_service_claim_during_custody_recovery_keeps_its_lease_for_the_parents_rebind(tmp_path: Path) -> None:
    with service_record_runtime(tmp_path) as runtime:
        service = runtime.connect_service()
        assert isinstance(runtime.admit(service), ServiceConnected)
        lease = service.claim()
        assert lease is not None

        def person_status() -> object:
            return runtime.human.session(
                SessionRequest(
                    action="session_status",
                    request_id=uuid4(),
                    profile_id=runtime.profile_id,
                    session_id=runtime.person_session_id,
                ),
                deadline=time.monotonic() + 10,
            )

        worker = runtime.profiles._profiles[runtime.profile_id].owner._worker
        assert worker is not None
        os.kill(worker._process.pid, signal.SIGTERM)
        deadline = time.monotonic() + 30
        while not (
            isinstance(status := person_status(), ProfileStatus)
            and status.status.denial is AccessDenialCode.CUSTODY_RECOVERING
        ):
            assert time.monotonic() < deadline, f"the runtime never suspended the person's lease: {status!r}"
            time.sleep(0.05)

        # A claim inside the window must neither re-approve nor withdraw the suspended child lease.
        assert service.claim() == lease
        assert service.connected is not None and service.connected.lease == lease

        rebound = login(runtime.human, runtime.profile_id, "password", PROFILE_INPUT.encode())
        assert isinstance(rebound, ProfileStatus) and rebound.status.denial is None, rebound
        assert rebound.status.session_id == runtime.person_session_id
        assert service.claim() == lease
        absent, material = service.record_read(RECORD_CAPABILITY, "synthetic-record")
        assert absent.state == "absent" and material == bytearray()
