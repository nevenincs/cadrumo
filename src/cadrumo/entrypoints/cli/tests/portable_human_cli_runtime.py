"""Joined, observable CLI integration with explicit synthetic OS custody loans.

The transport and physical worker isolation are test ports. Password proof,
human admission, registered operation execution and access guards are production
owners. This fixture proves those composed contracts, never native custody.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import sys
import time
import traceback
from collections.abc import AsyncIterator, Callable, Iterator, Sequence
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

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.posix_endpoint import PosixRuntimeEndpoint
from cadrumo.adapters.local_runtime.profile_worker_human_admission import ProfileWorkerHumanAdmission
from cadrumo.adapters.local_runtime.startup import RuntimeLaunchDoor
from cadrumo.adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.worker_authorization_client import WorkerAuthorizationClient
from cadrumo.adapters.local_runtime.worker_authorization_lease import WorkerAuthorizationLease
from cadrumo.adapters.local_runtime.worker_transport import WorkerChannel
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.portable_password_custody import portable_password_custody
from cadrumo.adapters.persistence.storage.master_key.active_session import (
    activate_session,
    current_active_bucket_session,
)
from cadrumo.adapters.persistence.storage.master_key.bucket_session import BucketSession
from cadrumo.adapters.persistence.storage.master_key.profile_worker_custody import ProfileWorkerCustody
from cadrumo.application.operator_surface.command_ports import ProfileAuthenticationPosture
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.application.runtime.profile_worker import ProfileWorkerIdentity
from cadrumo.application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationOwner,
    WorkerAutomationInventoryRequest,
)
from cadrumo.application.user_profile.access_contracts import (
    AccessSession,
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
    AutomationSecretStore,
)
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.core.config import load_settings
from cadrumo.core.time.clock import now
from cadrumo.core.time.utc import UtcInstant
from cadrumo.domain.calculations.registry.authority import published_authority_generation
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.runtime import session_owner, worker_service
from cadrumo.entrypoints.runtime.operation_host import ProfileWorkerOperationHost
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.profile_login import ProfileWorkerHumanLogin

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from .._profile_authentication_contract import profile_authentication_posture
from ..command_specs import COMMAND_GRAPH
from ..config import runtime_automation_request
from .cli_runner import ClickInvokeKwargs, invoke_cached_cli


class _Buffer:
    def __init__(self) -> None:
        self.condition = Condition()
        self.data = bytearray()
        self.closed = False


class _Channel:
    """Only memory bytes and finite waits; no socket, pipe or process launch."""

    def __init__(self, incoming: _Buffer, outgoing: _Buffer, peer: RuntimePeer) -> None:
        self.incoming, self.outgoing, self.peer = incoming, outgoing, peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        with self.incoming.condition:
            while len(self.incoming.data) < count:
                if self.incoming.closed:
                    raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                self.incoming.condition.wait(remaining)
            result = bytes(self.incoming.data[:count])
            del self.incoming.data[:count]
            return result

    def read_ready(self) -> bool:
        with self.incoming.condition:
            return bool(self.incoming.data) or self.incoming.closed

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        with self.outgoing.condition:
            if self.outgoing.closed:
                raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
            if time.monotonic() >= deadline:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            self.outgoing.data.extend(payload)
            self.outgoing.condition.notify_all()

    def close(self) -> None:
        for buffer in (self.incoming, self.outgoing):
            with buffer.condition:
                buffer.closed = True
                buffer.condition.notify_all()


def _channels(owner: str) -> tuple[_Channel, _Channel]:
    left, right = _Buffer(), _Buffer()
    peer = RuntimePeer(os_owner_id=owner, process_id=os.getpid())
    return _Channel(left, right, peer), _Channel(right, left, peer)


class _Listener:
    def __init__(self, storage_identity: str, owner: str) -> None:
        self.storage_identity, self.owner = storage_identity, owner
        self.pending: Queue[_Channel] = Queue()
        self.closed = False

    def listen(self) -> None:
        if self.closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    def accept(self, *, timeout: float) -> RuntimeByteChannel:
        try:
            return self.pending.get(timeout=timeout)
        except Empty:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None

    def connect(self, *, timeout: float) -> RuntimeByteChannel:
        del timeout
        if self.closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
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
        self.identity, self.root, self.oracle = identity, storage_root, oracle
        self.clock, self.monotonic = clock, monotonic
        self._leases: dict[UUID, AccessSession] = {}
        self._lock = RLock()
        self._closed = False
        self._sections = 0
        self._material_update_pending = False

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
    def _connection(self, channel: RuntimeByteChannel) -> None:
        self.test_context.copy().run(super()._connection, channel)


class _Authorization(WorkerAuthorizationClient):
    def __init__(self, identity: ProfileWorkerIdentity, root: Path, owner: WorkerAuthorizationOwner) -> None:
        super().__init__(identity=identity, root=root, parent_pid=os.getpid())
        self.owner = owner

    @override
    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncIterator[WorkerAuthorizationLease]:
        # The actual runtime owner evaluates and holds its thread-affine fence.
        with self.owner.authorize(request):
            yield WorkerAuthorizationLease(
                identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
            )

    @override
    async def inventory(self, request: WorkerAutomationInventoryRequest) -> AutomationInventory:
        with self.owner.automation_inventory(request) as allowed:
            return allowed.inventory


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
    ) -> None:
        del wall_clock
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
        # transport ports satisfy its RuntimeByteChannel framing contract.
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
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        if self._stopping.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)

    @override
    def close(self, *, deadline: float | None = None) -> None:
        self._stopping.set()
        if self._channel is not None:
            self._channel.close()
        if self._operation_channel is not None:
            self._operation_channel.close()
        try:
            self.running.result(timeout=15 if deadline is None else max(0, deadline - time.monotonic()))
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.CONNECTION_CLOSED:
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
            locked=False,
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
        arguments = list(args)
        spec = COMMAND_GRAPH.resolve_invocation(arguments)
        if (
            spec is None
            or profile_authentication_posture(COMMAND_GRAPH.node(spec.key))
            is not ProfileAuthenticationPosture.RESUME_FALLBACK
        ):
            return invoke_cached_cli(arguments, **kwargs)
        if any(
            token.startswith(("--profile-secrets-", "--profile-credential-ref", "--profile-auth-method"))
            for token in arguments
        ):
            return invoke_cached_cli(arguments, **kwargs)
        if "input" in kwargs and kwargs["input"] is not None:
            raise AssertionError(
                "human runtime will not overwrite explicit stdin; select its secret channel explicitly"
            )
        passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
        if "--profile" not in arguments:
            arguments[:0] = ["--profile", self.label]
        arguments[:0] = ["--profile-secrets-stdin"]
        invocation = cast(ClickInvokeKwargs, dict(kwargs))
        invocation["input"] = json.dumps({"profile_passphrase": passphrase})
        result = invoke_cached_cli(arguments, **invocation)
        assert passphrase not in result.output
        return result


@contextmanager
def portable_human_cli_runtime(
    *,
    storage_root: Path,
    profile_id: UUID,
    label: str,
    native_store: AutomationSecretStore | None = None,
    os_owner_id: str = "portable-test-owner",
    client_native_store: AutomationSecretStore | None = None,
) -> Iterator[PortableHumanCliRuntime]:
    """Own synthetic transport, real human admission and finite joined cleanup."""
    root = storage_root.resolve(strict=True)
    oracle = current_active_bucket_session()
    if oracle is None or oracle.bucket_id != str(profile_id):
        raise AssertionError("register the credential profile and retain its exact parent oracle first")
    endpoint = (
        WindowsRuntimeEndpoint(storage_root=root)
        if sys.platform == "win32"
        else PosixRuntimeEndpoint(storage_root=root)
    )
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
            patch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: client_native_store)
            patch.setattr(runtime_automation_request, "installed_automation_secret_store", lambda: client_native_store)

        async def open_transport(door: RuntimeLaunchDoor, *, timeout: float = 10) -> VerifiedRuntimeConnection:
            if door._expected.storage_identity != listener.storage_identity:
                raise RuntimeRefusalError(RuntimeRefusalCode.ROOT_MISMATCH)
            return await asyncio.to_thread(
                lambda: VerifiedRuntimeConnection(
                    listener.connect(timeout=timeout), expected=door._expected, deadline=time.monotonic() + timeout
                )
            )

        patch.setattr(RuntimeLaunchDoor, "open", open_transport)
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
