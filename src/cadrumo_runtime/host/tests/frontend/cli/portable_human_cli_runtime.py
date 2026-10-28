"""Joined, observable CLI integration with explicit synthetic OS custody loans.

The transport and physical worker isolation are test ports. Password proof,
human admission, registered operation execution and access guards are production
owners. This fixture proves those composed contracts, never native custody.

The profile's agent service is a test port too: a model run an operation sends
under its held START permit is answered by the stand-in that
:func:`serving_portable_agent` binds, as the runtime relays it to the profile's
admitted service. With none bound, the run is refused ``service_unavailable``,
which is what the runtime answers when no service is admitted.
"""

from __future__ import annotations

import asyncio
import hmac
import os
import sys
import time
import traceback
from collections.abc import AsyncGenerator, Callable, Generator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, contextmanager
from contextvars import Context, copy_context
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from queue import Empty, Queue
from threading import Condition, Event, RLock
from typing import Unpack, cast, override
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.outbound.llm.tests.model_run_support import RecordingModelRuns
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    activate_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.core.model_roles import ModelRole
from cadrumo.core.time.clock import now
from cadrumo.core.time.utc import UtcInstant
from cadrumo.domain.calculations.registry.authority_location import published_authority_generation
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.tests.cli_fixture_ports import ClickInvokeKwargs
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.contracts import (
    ByteChannel,
    ChannelWake,
    Peer,
    RefusalCode,
    RefusalError,
)
from cadrumo_client.contracts.model_runs import (
    ModelRunBody,
    ModelRunHeader,
    ModelRunOutcome,
    ModelRunRefusal,
    ModelRunRefusalCode,
    ModelRunServed,
    decode_model_run_body,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport import credentials
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.posix_endpoint import PosixEndpoint
from cadrumo_client.transport.startup import LaunchDoor
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.profile_worker_human_admission import ProfileWorkerHumanAdmission
from cadrumo_runtime.adapters.tests.profile_worker_support import NativeRuntimeFixtureOwner
from cadrumo_runtime.adapters.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo_runtime.adapters.worker_authorization_client import WorkerAuthorizationClient
from cadrumo_runtime.adapters.worker_authorization_lease import WorkerAuthorizationLease
from cadrumo_runtime.adapters.worker_transport import WorkerChannel
from cadrumo_runtime.commands import runtime_automation_request
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationOwner,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryRequest,
)
from cadrumo_runtime.host import session_owner, worker_service
from cadrumo_runtime.host.operation_host import ProfileWorkerOperationHost
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections
from cadrumo_runtime.host.profile_login import ProfileWorkerHumanLogin

from .profile_password_cli import invoke_with_profile_password


class _Buffer:
    def __init__(self) -> None:
        self.condition = Condition()
        self.data = bytearray()
        self.closed = False


class _Channel:
    """Only memory bytes and finite waits; no socket, pipe or process launch."""

    def __init__(self, incoming: _Buffer, outgoing: _Buffer, peer: Peer) -> None:
        self.incoming, self.outgoing, self.peer = incoming, outgoing, peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        with self.incoming.condition:
            while len(self.incoming.data) < count:
                if self.incoming.closed:
                    raise RefusalError(RefusalCode.CONNECTION_CLOSED)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
                self.incoming.condition.wait(remaining)
            result = bytes(self.incoming.data[:count])
            del self.incoming.data[:count]
            return result

    def read_ready(self) -> bool:
        with self.incoming.condition:
            return bool(self.incoming.data) or self.incoming.closed

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        while not self.read_ready():
            if any(wake.is_set() for wake in wakes):
                return False
            time.sleep(0.01)
        return True

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        with self.outgoing.condition:
            if self.outgoing.closed:
                raise RefusalError(RefusalCode.CONNECTION_CLOSED)
            if time.monotonic() >= deadline:
                raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)
            self.outgoing.data.extend(payload)
            self.outgoing.condition.notify_all()

    def close(self) -> None:
        for buffer in (self.incoming, self.outgoing):
            with buffer.condition:
                buffer.closed = True
                buffer.condition.notify_all()


def _channels(owner: str) -> tuple[_Channel, _Channel]:
    left, right = _Buffer(), _Buffer()
    peer = Peer(os_owner_id=owner, process_id=os.getpid())
    return _Channel(left, right, peer), _Channel(right, left, peer)


class _Listener:
    def __init__(self, storage_identity: str, owner: str) -> None:
        self.storage_identity, self.owner = storage_identity, owner
        self.pending: Queue[_Channel] = Queue()
        self.closed = False

    def listen(self) -> None:
        if self.closed:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def accept(self, *, timeout: float | None, wakes: tuple[ChannelWake, ...] = ()) -> ByteChannel:
        deadline = None if timeout is None else time.monotonic() + timeout
        while not any(wake.is_set() for wake in wakes):
            remaining = 0.01 if deadline is None else min(0.01, deadline - time.monotonic())
            if remaining <= 0:
                break
            try:
                return self.pending.get(timeout=remaining)
            except Empty:
                continue
        raise RefusalError(RefusalCode.DEADLINE_EXCEEDED)

    def connect(self, *, timeout: float) -> ByteChannel:
        del timeout
        if self.closed:
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        client, server = _channels(self.owner)
        self.pending.put(server)
        return client

    def close(self) -> None:
        self.closed = True
        while not self.pending.empty():
            self.pending.get_nowait().close()


class _LoanCustody(ProfileWorkerCustody):
    """Borrow one exact test oracle; retain all ordinary lease validation.

    No production worker binding is installed or reset. The fixture explicitly
    replaces process key ownership, and never closes the caller's oracle.
    """

    @override
    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        clock: Callable[[], UtcInstant] = now,
        monotonic: Callable[[], float] = time.monotonic,
        oracle: BucketSession | None = None,
    ) -> None:
        if oracle is None:
            oracle = current_active_bucket_session()
        if oracle is None:
            raise AssertionError("the portable custody loan requires its parent oracle")
        if oracle.bucket_id != str(identity.binding.profile_id):
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        self.oracle = oracle
        self._hold_nothing(identity, storage_root=storage_root, clock=clock, monotonic=monotonic)

    @override
    def _replace_key_session(self, leases: dict[UUID, AccessSession], dek: bytes) -> None:
        if not leases or not hmac.compare_digest(self.oracle.dek, dek):
            raise AutomationCustodyError(AutomationCustodyCode.CREDENTIAL_REJECTED)
        self._leases = leases

    @override
    def _release_material(self) -> None:
        # Ownership of physical key material remains with the test oracle.
        self._material_update_pending = False


class _ContextServer(RetainedRuntimeTransportServer):
    """Carry the fixture's configuration into each owned connection thread."""

    test_context: Context

    @override
    def _connection(self, channel: ByteChannel) -> None:
        self.test_context.copy().run(super()._connection, channel)


_SERVED_AGENTS: list[RecordingModelRuns] = []


@contextmanager
def serving_portable_agent(service: RecordingModelRuns) -> Generator[RecordingModelRuns]:
    """Answer every model run the portable runtime relays with ``service`` until the block exits."""
    _SERVED_AGENTS.append(service)
    try:
        yield service
    finally:
        _SERVED_AGENTS.remove(service)


async def _agent_answer(
    service: RecordingModelRuns, role: str | None, header: ModelRunHeader | None, body: ModelRunBody | None
) -> tuple[ModelRunOutcome, bytearray]:
    """Answer one lookup, selections read or run, in the outcome shape the service returns it."""
    if header is None:
        if role is None:
            selections = await service.selections()
            if isinstance(selections, ModelRunRefusal):
                return ModelRunOutcome(refusal=selections.code), bytearray()
            return ModelRunOutcome(selections=selections), bytearray()
        try:
            known = ModelRole(role)
        except ValueError:
            return ModelRunOutcome(refusal=ModelRunRefusalCode.UNKNOWN_ROLE), bytearray()
        lane = await service.lookup(known)
        if isinstance(lane, ModelRunRefusal):
            return ModelRunOutcome(refusal=lane.code), bytearray()
        return ModelRunOutcome(lane=lane), bytearray()
    if body is None:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    output = await service.run(header, body)
    if isinstance(output, ModelRunRefusal):
        return ModelRunOutcome(refusal=output.code), bytearray()
    text = bytearray(output.text.encode("utf-8"))
    served = ModelRunServed(
        provider_id=output.provider_id,
        transport=output.transport,
        model=output.model,
        agent_version=output.agent_version,
    )
    return ModelRunOutcome(served=served, text_byte_count=len(text)), text


class _ModelRunLease(WorkerAuthorizationLease):
    """A held permit whose one model run reaches the bound agent stand-in instead of a native channel."""

    _answered = False

    @override
    def model_run(
        self, role: str | None, header: ModelRunHeader | None, body: bytearray, *, answer_seconds: float
    ) -> tuple[ModelRunOutcome, bytearray]:
        del answer_seconds
        request = self.request
        try:
            # The production lease admits one run, only under a START permit.
            if (
                not isinstance(request, WorkerAuthorizationRequest)
                or request.request.action is not AccessAction.START
                or self._answered
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            self._answered = True
            decoded = None if header is None else decode_model_run_body(body)
        finally:
            body[:] = bytes(len(body))
        if not _SERVED_AGENTS:
            return ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE), bytearray()
        return asyncio.run(_agent_answer(_SERVED_AGENTS[-1], role, header, decoded))


class _Authorization(WorkerAuthorizationClient):
    def __init__(self, identity: ProfileWorkerIdentity, root: Path, owner: WorkerAuthorizationOwner) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.owner = owner

    @override
    async def check(self, request: WorkerAuthorityRequest) -> None:
        # The actual runtime owner evaluates admission and holds nothing once it answers.
        with self.owner.authorize(request):
            pass

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        # The actual runtime owner evaluates and holds its thread-affine fence.
        with self.owner.authorize(request):
            yield _ModelRunLease(connections=self.connections, request=request)

    @override
    async def inventory(self, request: WorkerAutomationInventoryRequest) -> AutomationInventory:
        with self.owner.automation_inventory(request) as allowed:
            return allowed.inventory

    @override
    def operations_advanced(self, operation_ids: tuple[OperationId, ...], *, records_changed: bool = False) -> None:
        # The runtime owner receives the worker's report as its endpoint would hand it on.
        self.owner.operations_advanced(operation_ids, records_changed=records_changed)


class _Worker(ProfileWorkerHumanAdmission):
    """Keep the production worker wire/service in an owned joined interpreter."""

    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        authorization: WorkerAuthorizationOwner | None = None,
        worker_script: Path | None = None,
        wall_clock=now,
        exited: Callable[[_Worker], None] | None = None,
    ) -> None:
        # The worker runs in a joined thread of this process: no process exit to watch.
        del wall_clock, exited
        if authorization is None or worker_script is not None:
            raise AssertionError("portable worker requires its runtime owner and no external script")
        oracle = current_active_bucket_session()
        if oracle is None:
            raise AssertionError("portable runtime requires its owned encrypted test oracle")
        self.identity = identity
        self._lock, self._operation_lock, self._human_lock = RLock(), RLock(), RLock()
        self._stopping = Event()
        self._human_candidate = None
        self._human_deadline = None
        control_client, control = _channels(identity.binding.os_owner_id)
        operation_client, operations = _channels(identity.binding.os_owner_id)
        # WorkerChannel names the production native union. These explicit test
        # transport ports satisfy its ByteChannel framing contract.
        self._channel = cast(WorkerChannel, control_client)
        self._operation_channel = cast(WorkerChannel, operation_client)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="portable-profile-worker")
        self.custody = _LoanCustody(identity, storage_root=storage_root, oracle=oracle)

        def run() -> None:
            with activate_session(oracle), profile_adapter_composition():
                client = _Authorization(identity, storage_root, authorization)
                host = ProfileWorkerOperationHost(self.custody, authorization=client)
                human = ProfileWorkerHumanLogin(self.custody, decode=host.profile_decode_context)
                try:
                    asyncio.run(
                        worker_service._serve(
                            cast(WorkerChannel, control), cast(WorkerChannel, operations), self.custody, human, host
                        )
                    )
                except BaseException as error:
                    print(
                        "portable worker diagnostic",
                        type(error).__name__,
                        [
                            (Path(frame.filename).name, frame.lineno, frame.name)
                            for frame in traceback.extract_tb(error.__traceback__)
                        ],
                        file=sys.stderr,
                    )
                    raise
                finally:
                    self.custody.close()

        context = copy_context()
        self.running = self.pool.submit(context.run, run)

    @override
    def _exchange_channel(self, operation: bool):
        self.require_alive()
        return self._operation_channel if operation else self._channel

    @override
    def require_alive(self) -> None:
        if self.running.done():
            self.running.result()
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)
        if self._stopping.is_set():
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    @override
    def close(self, *, deadline: float | None = None) -> None:
        self._stopping.set()
        if self._channel is not None:
            self._channel.close()
        if self._operation_channel is not None:
            self._operation_channel.close()
        try:
            self.running.result(timeout=15 if deadline is None else max(0, deadline - time.monotonic()))
        except RefusalError as error:
            if error.reason is not RefusalCode.CONNECTION_CLOSED:
                raise
        finally:
            if self.running.done():
                self.pool.shutdown(wait=True)

    @override
    def settle(self, *, deadline: float | None = None) -> None:
        self.close(deadline=deadline)


@dataclass(frozen=True)
class _Login:
    owner: str
    login_id: str

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@dataclass
class PortableHumanCliRuntime:
    """One password-authenticated frontend and retained local test oracle."""

    profile_id: UUID
    label: str

    def invoke(self, args: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        """Preserve explicit root options and add only a missing human source."""
        return invoke_with_profile_password(args, label=self.label, **kwargs)


@contextmanager
def portable_human_cli_runtime(
    *,
    storage_root: Path,
    profile_id: UUID,
    label: str,
    native_store: AutomationSecretStore | None = None,
    os_owner_id: str = "portable-test-owner",
    client_native_store: AutomationSecretStore | None = None,
) -> Generator[PortableHumanCliRuntime]:
    """Own synthetic transport, real human admission and finite joined cleanup."""
    root = storage_root.resolve(strict=True)
    oracle = current_active_bucket_session()
    if oracle is None or oracle.bucket_id != str(profile_id):
        raise AssertionError("register the credential profile and retain its exact parent oracle first")
    endpoint = WindowsEndpoint(storage_root=root) if sys.platform == "win32" else PosixEndpoint(storage_root=root)
    listener = _Listener(endpoint.storage_identity, os_owner_id)
    stop, boot = Event(), uuid4()
    login = _Login(listener.owner, str(uuid4()))
    native = MemoryNativePort() if native_store is None else native_store
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=listener.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=lambda _: login,
        secret_store=lambda: native,
    )
    server = _ContextServer(
        listener,
        product_version=version("cadrumo"),
        stop=stop,
        profiles=profiles,
        boot_id=boot,
        authority_generation=published_authority_generation(),
    )
    server.test_context = copy_context()
    owner = NativeRuntimeFixtureOwner(listener, stop, timeout=20)
    primary: BaseException | None = None
    with portable_password_custody(), pytest.MonkeyPatch.context() as patch:
        patch.setattr(session_owner, "ProfileWorkerProcess", _Worker)
        if client_native_store is not None:
            patch.setattr(credentials, "installed_automation_secret_store", lambda: client_native_store)
            patch.setattr(runtime_automation_request, "installed_automation_secret_store", lambda: client_native_store)

        async def open_transport(door: LaunchDoor, *, timeout: float = 10) -> VerifiedConnection:
            if door._expected.storage_identity != listener.storage_identity:
                raise RefusalError(RefusalCode.ROOT_MISMATCH)
            return await asyncio.to_thread(
                lambda: VerifiedConnection(
                    listener.connect(timeout=timeout), expected=door._expected, deadline=time.monotonic() + timeout
                )
            )

        patch.setattr(LaunchDoor, "open", open_transport)
        owner.server = server
        owner.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="portable-runtime")
        context = copy_context()

        def run_server() -> None:
            context.run(server.serve)

        owner.running = owner.executor.submit(run_server)
        try:
            assert server.ready.wait(3)
            yield PortableHumanCliRuntime(profile_id, label)
        except BaseException as error:
            primary = error
            raise
        finally:
            owner.close_from_sync(task_name="portable-human-runtime-close", primary_error=primary)
            endpoint.close()
            assert current_active_bucket_session() is oracle, "portable runtime must preserve the parent oracle"
