"""Runtime-owned profile worker launch and authenticated channel ownership transfer."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from datetime import datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event, RLock
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError, RuntimeServerHello
from ...application.runtime.profile_worker import (
    ProfileWorkerIdentity,
)
from ...application.runtime.worker_authorization import WorkerAuthorizationOwner
from ...core.async_cleanup import AsyncResourceCleanupError
from ...core.config import Settings
from ...core.storage_environment import storage_directory
from ...core.time.clock import now
from .framing import accept_runtime_handshake
from .linux_worker_process import LinuxOwnedProcess, LinuxProcessScope
from .profile_worker_human_admission import ProfileWorkerHumanAdmission
from .runtime_frame_io import read_document, write_document
from .windows_process import WindowsOwnedProcess, WindowsProcessScope, unreturned_windows_process_scope
from .worker_authorization import WorkerAuthorizationServer
from .worker_native_identity import worker_operation_namespace
from .worker_resource_cleanup import WorkerResourceCleanup, release_worker_resources
from .worker_transport import WorkerChannel, WorkerEndpoint, worker_endpoint

_WORKER_STARTUP_ACCEPT_TIMEOUT_SECONDS = 45.0


_WORKER_STARTUP_ACCEPT_POLL_SECONDS = 0.1


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
    _scope: WindowsProcessScope | LinuxProcessScope
    _process: WindowsOwnedProcess | LinuxOwnedProcess
    _authorization: WorkerAuthorizationServer | None

    def __init__(
        self,
        identity: ProfileWorkerIdentity,
        *,
        storage_root: Path,
        authorization: WorkerAuthorizationOwner | None = None,
        worker_script: Path | None = None,
        wall_clock: Callable[[], datetime] = now,
    ) -> None:
        """Launch and authenticate a contained installed worker before key access."""
        if sys.platform not in {"win32", "linux"}:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
        if worker_script is not None:
            worker_script = worker_script.resolve(strict=True)
        self.identity = identity
        self._lock = RLock()
        self._operation_lock = RLock()
        self._human_lock = RLock()
        self._native_guard = RLock()
        self._stopping = Event()
        self._channel: WorkerChannel | None = None
        self._operation_channel: WorkerChannel | None = None
        self._human_candidate: UUID | None = None
        self._human_deadline: float | None = None
        self._authorization = None
        endpoint = worker_endpoint(storage_root=storage_root, worker_namespace=identity.worker_id)
        operation_endpoint = worker_endpoint(
            storage_root=storage_root, worker_namespace=worker_operation_namespace(identity.worker_id)
        )
        endpoint_owner = WorkerResourceCleanup(endpoint.close)
        operation_endpoint_owner = WorkerResourceCleanup(operation_endpoint.close)
        self._listener_cleanup = (endpoint_owner, operation_endpoint_owner)
        self._pending_channel_cleanup: list[WorkerResourceCleanup] = []
        try:
            self._scope = (
                WindowsProcessScope()
                if sys.platform == "win32"
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
            environment = _worker_launch_environment(storage_root=storage_root)
            environment["PYDANTIC_DISABLE_PLUGINS"] = "__all__"
            product_version = version("cadrumo")
            worker_entrypoint = (
                ("-m", "cadrumo.entrypoints.runtime.worker")
                if worker_script is None
                else (str(worker_script.resolve(strict=True)),)
            )
            self._process = self._scope.launch(
                executable=Path(sys.executable),
                arguments=(
                    "-I",
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
            # A cold isolated worker imports the registered operation catalogue
            # before opening its first pipe. Keep that bounded startup budget
            # separate from the short handshakes after the pipe is connected.
            self._open_worker_channels(
                endpoint, operation_endpoint, storage_root, identity, authorization, wall_clock, product_version
            )
            # Construction transfers the child only after both native listeners
            # have retired. A release failure must not lose the unreturned owner.
            retiring_listeners = True
            try:
                release_worker_resources(endpoint_owner, operation_endpoint_owner)
            except AsyncResourceCleanupError as cleanup:
                error = RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                error.__dict__["async_cleanup_error"] = cleanup
                raise error from cleanup
        except BaseException as error:
            # Callback settlement needs the caller's profile guard released.
            # Retain this candidate for adoption before a refusal is projected.
            error.__dict__["_profile_worker_candidate"] = self
            owners = (WorkerResourceCleanup(lambda: self._close_resources(deadline=None, retire_listeners=False)),)
            if not retiring_listeners:
                owners += (endpoint_owner, operation_endpoint_owner)
            release_worker_resources(*owners, primary_error=error)
            raise

    def _accept_startup_channel(
        self,
        endpoint: WorkerEndpoint,
        *,
        timeout: float,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> WorkerChannel:
        deadline = monotonic() + timeout
        while True:
            self._require_process_alive()
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            try:
                channel = endpoint.accept(timeout=min(_WORKER_STARTUP_ACCEPT_POLL_SECONDS, remaining))
            except RuntimeRefusalError as error:
                if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
                self._require_process_alive()
                continue
            try:
                self._require_process_alive()
            except BaseException as error:
                owner = WorkerResourceCleanup(channel.close)
                self._pending_channel_cleanup.append(owner)
                release_worker_resources(owner, primary_error=error)
                raise
            return channel

    def _open_worker_channels(
        self,
        endpoint: WorkerEndpoint,
        operation_endpoint: WorkerEndpoint,
        storage_root: Path,
        identity: ProfileWorkerIdentity,
        authorization: WorkerAuthorizationOwner | None,
        wall_clock: Callable[[], datetime],
        product_version: str,
    ) -> None:
        """Authenticate both retained channels before listener ownership is transferred."""
        channel = self._accept_startup_channel(endpoint, timeout=_WORKER_STARTUP_ACCEPT_TIMEOUT_SECONDS)
        self._channel = channel
        worker_process_id = self._verify_native_peer(channel)
        deadline = time.monotonic() + 10
        accept_runtime_handshake(
            channel,
            identity=RuntimeServerHello(
                product_version=product_version,
                storage_identity=endpoint.storage_identity,
                boot_id=identity.runtime_boot_id,
            ),
            deadline=deadline,
        )
        write_document(channel, identity, deadline=deadline)
        accepted = read_document(channel, ProfileWorkerIdentity, deadline=deadline)
        if accepted != identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._authorization = WorkerAuthorizationServer(
            identity=identity,
            root=storage_root,
            process_id=worker_process_id,
            owns_process=self._owns_native_process,
            contain=self._contain_native_process,
            owner=authorization,
            wall_clock=wall_clock,
        )
        operation_channel = self._accept_startup_channel(operation_endpoint, timeout=10)
        self._operation_channel = operation_channel
        if operation_channel.peer != channel.peer:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if isinstance(self._scope, LinuxProcessScope):
            self._verify_native_peer(operation_channel)
        deadline = time.monotonic() + 10
        accept_runtime_handshake(
            operation_channel,
            identity=RuntimeServerHello(
                product_version=product_version,
                storage_identity=operation_endpoint.storage_identity,
                boot_id=identity.runtime_boot_id,
            ),
            deadline=deadline,
        )
        write_document(operation_channel, identity, deadline=deadline)
        if read_document(operation_channel, ProfileWorkerIdentity, deadline=deadline) != identity:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


def _worker_launch_environment(*, storage_root: Path) -> dict[str, str]:
    """Retain storage controls and bind scratch storage across the isolated worker boundary."""
    if sys.platform == "win32":
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith(("PYTHON", "LD_", "DYLD_"))
        }
    else:
        environment = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
        storage_names = Settings.storage_env_var_names()
        environment.update({key: value for key, value in os.environ.items() if key in storage_names})
    temporary_root = storage_directory("CADRUMO_TEMP_DIR", "tmp", root=storage_root)
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    environment.update({name: str(temporary_root) for name in ("TEMP", "TMP", "TMPDIR")})
    return environment
