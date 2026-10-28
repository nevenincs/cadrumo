"""Runtime-owned profile worker launch and authenticated channel ownership transfer."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import datetime
from importlib.metadata import version
from logging import WARNING
from pathlib import Path
from threading import RLock, Thread, Timer
from uuid import UUID

from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo.core.package_interpreter import interpreter_command
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import ChannelWake, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.deadline_budget import (
    DEFAULT_TIMEOUT_POLICY,
    OrchestrationTimeoutError,
    TimeoutDeadline,
)
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.windows_process import (
    WindowsOwnedProcess,
    WindowsProcessScope,
    unreturned_windows_process_scope,
)
from cadrumo_runtime.adapters.connection_handshake import accept_connection_handshake
from cadrumo_runtime.contracts.profile_worker import ProfileWorkerReady
from cadrumo_runtime.contracts.worker_authorization import WorkerAuthorizationOwner

from .linux_worker_process import LinuxOwnedProcess, LinuxProcessScope
from .macos_worker_process import MacosOwnedProcess, MacosProcessScope
from .profile_worker_human_admission import ProfileWorkerHumanAdmission
from .worker_authorization import WorkerAuthorizationServer
from .worker_native_identity import worker_operation_namespace, worker_proof_namespace
from .worker_resource_cleanup import WorkerResourceCleanup, release_worker_resources
from .worker_transport import WorkerChannel, WorkerEndpoint, worker_endpoint

_LOGGER = get_logger(__name__)


def unreturned_profile_worker(error: BaseException) -> ProfileWorkerProcess | None:
    """Find the native owner a failed constructor could not return to its caller."""
    candidate = error.__dict__.get("_profile_worker_candidate")
    return candidate if isinstance(candidate, ProfileWorkerProcess) else None


class ProfileWorkerProcess(ProfileWorkerHumanAdmission):
    """One immutable profile process and its parent-owned containment scope.

    This is a custody transport, not an admission service. Only the runtime's
    session authority may supply a lease or key. Construction sends no secrets.
    """

    identity: ProfileWorkerIdentity
    _lock: RLock
    _operation_lock: RLock
    _scope: WindowsProcessScope | LinuxProcessScope | MacosProcessScope
    _process: WindowsOwnedProcess | LinuxOwnedProcess | MacosOwnedProcess
    _authorization: WorkerAuthorizationServer | None

    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        authorization: WorkerAuthorizationOwner | None = None,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
        exited: Callable[[ProfileWorkerProcess], None] | None = None,
        stopping: ChannelWake | None = None,
    ) -> None:
        """Launch and authenticate a contained installed worker before key access.

        ``exited`` hears, from a watch thread, that the worker exited before
        anything stopped it; an exit after ``close`` began is not reported.
        """
        if sys.platform not in {"win32", "linux", "darwin"}:
            raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
        if worker_script is not None:
            worker_script = worker_script.resolve(strict=True)
        self.identity = identity
        self._lock = RLock()
        self._operation_lock = RLock()
        self._human_lock = RLock()
        self._native_guard = RLock()
        self._native_activity_lock = RLock()
        self._native_activity = None
        self._stopping = NativeWake()
        self._owner_stopping = stopping
        self._process_exited = NativeWake()
        self._startup_expired = NativeWake()
        self._startup_deadline = DEFAULT_TIMEOUT_POLICY.deadline()
        self._channel: WorkerChannel | None = None
        self._operation_channel: WorkerChannel | None = None
        self._proof_channel = None
        self._human_candidate: UUID | None = None
        self._human_deadline: float | None = None
        self._human_transaction_deadline: float | None = None
        self._authorization = None
        endpoint = worker_endpoint(storage_root=storage_root, worker_namespace=identity.worker_id)
        operation_endpoint = worker_endpoint(
            storage_root=storage_root, worker_namespace=worker_operation_namespace(identity.worker_id)
        )
        proof_endpoint = worker_endpoint(
            storage_root=storage_root, worker_namespace=worker_proof_namespace(identity.worker_id)
        )
        endpoint_owner = WorkerResourceCleanup(endpoint.close)
        operation_endpoint_owner = WorkerResourceCleanup(operation_endpoint.close)
        proof_endpoint_owner = WorkerResourceCleanup(proof_endpoint.close)
        self._listener_cleanup = (endpoint_owner, operation_endpoint_owner, proof_endpoint_owner)
        self._pending_channel_cleanup: list[WorkerResourceCleanup] = []
        try:
            self._scope = (
                WindowsProcessScope()
                if sys.platform == "win32"
                else MacosProcessScope(
                    worker_id=identity.worker_id, storage_root=storage_root, worker_script=worker_script
                )
                if sys.platform == "darwin"
                else LinuxProcessScope(worker_id=identity.worker_id, worker_script=worker_script)
            )
        except BaseException as error:
            retained_scope = unreturned_windows_process_scope(error)
            if retained_scope is not None:
                # Native construction already attempted release. Transfer its
                # actual remaining owner before a public refusal drops errors.
                self._scope = retained_scope
                self._stopping.set()
                error.__dict__["_profile_worker_candidate"] = self
            raise
        retiring_listeners = False
        try:
            endpoint.listen()
            operation_endpoint.listen()
            proof_endpoint.listen()
            environment = _worker_launch_environment(storage_root=storage_root, profile_id=identity.binding.profile_id)
            environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
            product_version = version("cadrumo")
            worker_entrypoint = (
                ("-m", "cadrumo_runtime.host.worker")
                if worker_script is None
                else (str(worker_script.resolve(strict=True)),)
            )
            interpreter, *interpreter_arguments = interpreter_command()
            self._process = self._scope.launch(
                executable=Path(interpreter),
                arguments=(
                    *interpreter_arguments,
                    "-I",
                    "-B",
                    *worker_entrypoint,
                    "--storage-root",
                    str(storage_root),
                    "--worker-id",
                    str(identity.worker_id),
                    "--parent-pid",
                    str(os.getpid()),
                    "--expected-version",
                    product_version,
                ),
                directory=storage_root,
                environment=environment,
            )
            self._watch_exit(exited)
            startup_watchdog = Timer(self._startup_deadline.remaining_seconds(), self._startup_expired.set)
            startup_watchdog.daemon = True
            startup_watchdog.start()
            try:
                self._open_worker_channels(
                    endpoint,
                    operation_endpoint,
                    proof_endpoint,
                    storage_root,
                    identity,
                    authorization,
                    wall_clock,
                    product_version,
                )
            finally:
                startup_watchdog.cancel()
            self._require_process_alive()
            # Construction transfers the child only after all native listeners
            # have retired. A release failure must not lose the unreturned owner.
            retiring_listeners = True
            try:
                release_worker_resources(endpoint_owner, operation_endpoint_owner, proof_endpoint_owner)
            except AsyncResourceCleanupError as cleanup:
                error = RefusalError(RefusalCode.UNAVAILABLE)
                error.__dict__["async_cleanup_error"] = cleanup
                raise error from cleanup
            self._start_proof_dispatcher()
        except BaseException as error:
            # Callback settlement needs the caller's profile guard released.
            # Retain this candidate for adoption before a refusal is projected.
            error.__dict__["_profile_worker_candidate"] = self
            owners = (WorkerResourceCleanup(lambda: self._close_resources(deadline=None, retire_listeners=False)),)
            if not retiring_listeners:
                owners += (endpoint_owner, operation_endpoint_owner, proof_endpoint_owner)
            release_worker_resources(*owners, primary_error=error)
            raise

    def _watch_exit(self, exited: Callable[[ProfileWorkerProcess], None] | None) -> None:
        """Report an unrequested exit as soon as the process ends, not when a later exchange fails.

        Only a Windows process offers a wait handle independent of the scope's
        own; elsewhere the health checks of later exchanges establish the loss.
        """
        process = self._process
        try:
            waiter = process.retain_waiter() if isinstance(process, WindowsOwnedProcess) else process
        except Exception as error:
            diagnostic_event(_LOGGER, "profile_worker_exit_watch_unavailable", primary_error=error, level=WARNING)
            return
        watch = Thread(target=self._await_exit, args=(waiter, exited), name="profile-worker-exit-watch", daemon=True)
        try:
            watch.start()
        except BaseException as error:
            if isinstance(waiter, WindowsOwnedProcess):
                waiter.close()
            diagnostic_event(_LOGGER, "profile_worker_exit_watch_unavailable", primary_error=error, level=WARNING)

    def _await_exit(
        self,
        waiter: WindowsOwnedProcess | LinuxOwnedProcess | MacosOwnedProcess,
        exited: Callable[[ProfileWorkerProcess], None] | None,
    ) -> None:
        try:
            if isinstance(waiter, WindowsOwnedProcess):
                waiter.wait(timeout=None)
            else:
                waiter.wait(timeout=self._startup_deadline.remaining_seconds())
            self._process_exited.set()
            if not self._stopping.is_set() and exited is not None:
                exited(self)
        except (RefusalError, OrchestrationTimeoutError):
            return
        finally:
            if isinstance(waiter, WindowsOwnedProcess):
                waiter.close()

    def _accept_startup_channel(
        self,
        endpoint: WorkerEndpoint,
        *,
        deadline: TimeoutDeadline,
    ) -> WorkerChannel:
        wakes = self._startup_wakes()
        try:
            self._require_process_alive()
            self._require_startup_wait()
            deadline.remaining_seconds()
            channel = endpoint.accept(timeout=None, wakes=wakes)
        except RefusalError as error:
            self._require_startup_wait()
            raise error
        except OrchestrationTimeoutError as error:
            raise RefusalError(RefusalCode.TIMEOUT) from error
        try:
            self._require_process_alive()
            self._require_startup_wait()
            try:
                deadline.remaining_seconds()
            except OrchestrationTimeoutError as error:
                raise RefusalError(RefusalCode.TIMEOUT) from error
        except BaseException as error:
            owner = WorkerResourceCleanup(channel.close)
            self._pending_channel_cleanup.append(owner)
            release_worker_resources(owner, primary_error=error)
            raise
        return channel

    def _startup_wakes(self) -> tuple[ChannelWake, ...]:
        wakes: tuple[ChannelWake, ...] = (self._stopping, self._process_exited, self._startup_expired)
        if self._owner_stopping is not None:
            wakes += (self._owner_stopping,)
        return wakes

    def _require_startup_wait(self) -> None:
        if self._startup_expired.is_set():
            raise RefusalError(RefusalCode.TIMEOUT)
        if (
            self._stopping.is_set()
            or self._process_exited.is_set()
            or (self._owner_stopping is not None and self._owner_stopping.is_set())
        ):
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def _wait_startup_input(self, channel: WorkerChannel) -> None:
        self._require_startup_wait()
        if not channel.wait_readable(*self._startup_wakes()):
            self._require_startup_wait()
            raise RefusalError(RefusalCode.CONNECTION_CLOSED)

    def _open_worker_channels(
        self,
        endpoint: WorkerEndpoint,
        operation_endpoint: WorkerEndpoint,
        proof_endpoint: WorkerEndpoint,
        storage_root: Path,
        identity: ProfileWorkerIdentity,
        authorization: WorkerAuthorizationOwner | None,
        wall_clock: Callable[[], datetime],
        product_version: str,
    ) -> None:
        """Authenticate both retained channels before listener ownership is transferred."""
        channel = self._accept_startup_channel(endpoint, deadline=self._startup_deadline)
        self._channel = channel
        worker_process_id = self._verify_native_peer(channel)
        deadline = self._startup_deadline.instant
        self._wait_startup_input(channel)
        accept_connection_handshake(
            channel,
            identity=ServerHello(
                product_version=product_version,
                storage_identity=endpoint.storage_identity,
                boot_id=identity.runtime_boot_id,
            ),
            deadline=deadline,
        )
        write_document(channel, identity, deadline=deadline)
        self._wait_startup_input(channel)
        accepted = read_document(channel, ProfileWorkerIdentity, deadline=deadline)
        if accepted != identity:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._authorization = WorkerAuthorizationServer(
            identity=identity,
            root=storage_root,
            process_id=worker_process_id,
            owns_process=self._owns_native_process,
            contain=self._contain_native_process,
            owner=authorization,
            wall_clock=wall_clock,
        )
        operation_channel = self._accept_startup_channel(operation_endpoint, deadline=self._startup_deadline)
        self._operation_channel = operation_channel
        if operation_channel.peer != channel.peer:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        self._verify_native_peer(operation_channel)
        deadline = self._startup_deadline.instant
        self._wait_startup_input(operation_channel)
        accept_connection_handshake(
            operation_channel,
            identity=ServerHello(
                product_version=product_version,
                storage_identity=operation_endpoint.storage_identity,
                boot_id=identity.runtime_boot_id,
            ),
            deadline=deadline,
        )
        write_document(operation_channel, identity, deadline=deadline)
        self._wait_startup_input(operation_channel)
        if read_document(operation_channel, ProfileWorkerIdentity, deadline=deadline) != identity:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        proof_channel = self._accept_startup_channel(proof_endpoint, deadline=self._startup_deadline)
        self._proof_channel = proof_channel
        if proof_channel.peer != channel.peer:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        self._verify_native_peer(proof_channel)
        self._wait_startup_input(proof_channel)
        accept_connection_handshake(
            proof_channel,
            identity=ServerHello(
                product_version=product_version,
                storage_identity=proof_endpoint.storage_identity,
                boot_id=identity.runtime_boot_id,
            ),
            deadline=deadline,
        )
        write_document(proof_channel, identity, deadline=deadline)
        self._wait_startup_input(proof_channel)
        if read_document(proof_channel, ProfileWorkerIdentity, deadline=deadline) != identity:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._wait_startup_input(channel)
        ready = read_document(channel, ProfileWorkerReady, deadline=deadline)
        if ready.identity != identity:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED, check="worker_ready_identity")


def _worker_launch_environment(*, storage_root: Path, profile_id: UUID) -> dict[str, str]:
    """Pin the storage root and keep operator storage controls across the isolated worker boundary.

    POSIX workers start from a fixed noncredential environment; Windows workers
    keep the ambient environment minus the declared cleared classes. A worker
    serves exactly one profile, and is told that profile's folder.
    """
    posix_base = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
    environment = child_environment(
        ChildEnvironmentProfile.OPERATOR,
        storage_root,
        base=None if sys.platform == "win32" else posix_base,
        sys_platform=sys.platform,
        profile_id=profile_id,
    )
    return environment
