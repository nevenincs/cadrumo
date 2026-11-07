"""Shared native fault seams for the profile worker transfer and shutdown tests."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Mapping, Sequence
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import BinaryIO, override
from uuid import uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.user_profile.access_contracts import (
    ProfileAccessBinding,
)
from cadrumo.core.async_cleanup import AsyncResourceCleanupError
from cadrumo_client.contracts.contracts import ChannelWake, ClientHello, Peer, RefusalCode, RefusalError
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import document_frame, read_document, write_document
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_client.transport.windows_channel import WindowsChannel
from cadrumo_client.transport.windows_owned_process import WindowsOwnedProcess
from cadrumo_client.transport.windows_process import WindowsProcessScope
from cadrumo_runtime.contracts.profile_worker import (
    ProfileWorkerHumanOutcome,
    ProfileWorkerProofAcknowledged,
    ProfileWorkerProofControl,
    ProfileWorkerReady,
    ProfileWorkerRefusal,
    ProfileWorkerRequest,
    ProfileWorkerStatus,
)

from .. import profile_worker
from ..profile_worker import ProfileWorkerProcess
from ..worker_authorization import WorkerAuthorizationServer


class NativePeerError(Exception):
    """An explicit native acquisition failure, portable across test platforms."""


class NativePeerProcess:
    """Record native process handle acquisition without querying a synthetic PID."""

    HANDLE = 4321

    QUERY_RIGHTS = 0x400 | 0x100000

    def __init__(self) -> None:

        self.opened = 0

        self.closed = 0

    def open(self, rights: int, inherit: bool, process_id: int) -> int:

        assert rights == self.QUERY_RIGHTS and not inherit

        if process_id != 1234:
            raise NativePeerError("synthetic peer process absent")

        self.opened += 1

        return self.HANDLE

    def close(self, handle: int) -> None:

        assert handle == self.HANDLE and self.closed < self.opened

        self.closed += 1


class Release:
    def __init__(self, failures: int = 0) -> None:

        self.failures = failures

        self.calls = 0

        self.released = False

        self.failure = OSError("synthetic owned release failure")

    def __call__(self) -> None:

        self.calls += 1

        if self.calls <= self.failures:
            raise self.failure

        self.released = True


class Channel(WindowsChannel):
    def __init__(
        self, identity: ProfileWorkerIdentity, *, foreign_version: bool = False, proof_control: bool = False
    ) -> None:

        self.identity = identity

        self.proof_control = proof_control

        self.release = Release()

        self.inbound = bytearray()

        self.writes: list[bytes] = []

        self.read_failure: BaseException | None = None

        self.before_read: Callable[[], None] | None = None

        self.native_peer = Peer(os_owner_id="synthetic-owner", process_id=1234)

        self.incarnation_matches = True

        self.peer_checks = 0

        for document in (
            ClientHello(product_version="foreign" if foreign_version else "worker-test", storage_identity="a" * 64),
            identity,
        ):
            write_document(self, document, deadline=time.monotonic() + 5)

        self.inbound.extend(b"".join(self.writes))

        self.writes.clear()

    @property
    @override
    def peer(self) -> Peer:

        return self.native_peer

    @override
    def verify_peer_process(self, process_handle: int) -> None:

        assert process_handle == NativePeerProcess.HANDLE

        self.peer_checks += 1

        if not self.incarnation_matches:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)

    @override
    def read_exact(self, count: int, *, deadline: float) -> bytes:

        assert deadline > time.monotonic()

        if self.before_read is not None:
            self.before_read()

        if self.read_failure is not None:
            raise self.read_failure

        assert len(self.inbound) >= count

        value = bytes(self.inbound[:count])

        del self.inbound[:count]

        return value

    @override
    def read_ready(self) -> bool:

        return bool(self.inbound)

    @override
    def wait_readable(self, *wakes: ChannelWake) -> bool:

        while not self.read_ready():
            if any(wake.is_set() for wake in wakes):
                return False

            time.sleep(0.01)

        return True

    @override
    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:

        assert deadline > time.monotonic()

        self.writes.append(bytes(payload))

        if self.proof_control:
            try:
                request = ProfileWorkerProofControl.model_validate_json(payload[5:])

            except ValidationError:
                return

            self.inbound.extend(
                document_frame(
                    ProfileWorkerProofAcknowledged(
                        identity=self.identity,
                        request_id=request.request_id,
                        proof_attempt_id=request.proof_attempt_id,
                    )
                )
            )

    @override
    def close(self) -> None:

        self.release()


class Endpoint(WindowsEndpoint):
    def __init__(self, channel: Channel) -> None:

        self.channel = channel

        self.release = Release()

        self.storage_identity = "a" * 64

        self.listen_failure: BaseException | None = None

        self.before_accept: Callable[[], None] | None = None

    @override
    def listen(self) -> None:

        if self.listen_failure is not None:
            raise self.listen_failure

    @override
    def accept(self, *, timeout: float | None = 5.0, wakes: tuple[ChannelWake, ...] = ()) -> WindowsChannel:

        # Startup waits on actual connection, process exit, owner stop, or the

        # separately armed timeout watchdog; no polling budget is supplied.

        assert timeout is None

        assert len(wakes) >= 3

        if self.before_accept is not None:
            self.before_accept()

        return self.channel

    @override
    def close(self) -> None:

        self.release()


class Child(WindowsOwnedProcess):
    def __init__(self) -> None:

        self.exited = False

        self.wait_calls = 0

    @override
    def wait(self, *, timeout: float | None) -> int:

        assert timeout is not None, "profile worker startup must bound process waits"

        self.wait_calls += 1

        if self.exited:
            return 1

        raise RefusalError(RefusalCode.TIMEOUT)


class Scope(WindowsProcessScope):
    def __init__(self) -> None:

        self.release = Release()

        self.launched = False

        self.timeouts: list[float] = []

        self.refuse_zero_timeout = False

        self.child = Child()

        self.native_member = True

        self.membership_checks = 0

        self.worker_script: Path | None = None

        self.launch_arguments: tuple[str, ...] | None = None

        self.launch_directory: Path | None = None

        self.launch_environment: dict[str, str] | None = None

    @override
    def contains_process(self, process_handle: int) -> bool:

        assert process_handle == NativePeerProcess.HANDLE

        self.membership_checks += 1

        return self.native_member and self.launched and not self.release.released

    @override
    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> WindowsOwnedProcess:

        assert executable == Path(sys.executable)

        prefix = (
            ("-I", "-B", "-m", "cadrumo_runtime.host.worker")
            if self.worker_script is None
            else ("-I", "-B", str(self.worker_script.resolve(strict=True)))
        )

        assert tuple(arguments[: len(prefix)]) == prefix

        self.launch_arguments = tuple(arguments)

        self.launch_directory = directory

        self.launch_environment = dict(environment)

        self.launched = True

        return self.child

    @override
    def launch_with_standard_error(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> tuple[WindowsOwnedProcess, BinaryIO]:

        child = self.launch(executable=executable, arguments=arguments, directory=directory, environment=environment)

        return child, BytesIO()

    @override
    def active_process_ids(self) -> tuple[int, ...]:

        return (1234,) if self.launched and not self.release.released else ()

    @override
    def terminate(self, *, timeout: float = 2) -> None:

        assert timeout >= 0

        self.timeouts.append(timeout)

        if self.refuse_zero_timeout and timeout == 0:
            raise RefusalError(RefusalCode.TIMEOUT)

        self.release()


class Authorization(WorkerAuthorizationServer):
    def __init__(self) -> None:

        self.release = Release()

        self.health_failure: RefusalCode | None = None

        self.health_calls = 0

    @override
    def close(self) -> None:

        self.release()

    @override
    def require_healthy(self) -> None:

        self.health_calls += 1

        if self.health_failure is not None:
            raise RefusalError(self.health_failure)

        assert not self.release.released


class Fixture:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, root: Path, *, foreign_version: bool = False) -> None:

        self.root = root

        self.identity = ProfileWorkerIdentity(
            worker_id=uuid4(),
            runtime_boot_id=uuid4(),
            binding=ProfileAccessBinding(
                profile_id=uuid4(),
                installation_id=uuid4(),
                os_owner_id="synthetic-owner",
                custody_generation=1,
                dek_epoch=uuid4(),
            ),
        )

        self.channels = (
            Channel(self.identity, foreign_version=foreign_version),
            Channel(self.identity),
            Channel(self.identity, proof_control=True),
        )

        write_document(self.channels[0], ProfileWorkerReady(identity=self.identity), deadline=time.monotonic() + 5)

        self.channels[0].inbound.extend(b"".join(self.channels[0].writes))

        self.channels[0].writes.clear()

        self.endpoints = tuple(Endpoint(channel) for channel in self.channels)

        self.scope = Scope()

        self.authorization = Authorization()

        self.native_process = NativePeerProcess()

        api = ModuleType("win32api")

        api.__dict__.update(OpenProcess=self.native_process.open, CloseHandle=self.native_process.close)

        constants = ModuleType("win32con")

        constants.__dict__.update(PROCESS_QUERY_INFORMATION=0x400, SYNCHRONIZE=0x100000)

        errors = ModuleType("pywintypes")

        errors.__dict__["error"] = NativePeerError

        for module in (api, constants, errors):
            monkeypatch.setitem(sys.modules, module.__name__, module)

        pending = iter(self.endpoints)

        monkeypatch.setattr(
            profile_worker,
            "sys",
            SimpleNamespace(platform="win32", executable=sys.executable, prefix=sys.prefix, base_prefix=sys.prefix),
        )

        monkeypatch.setattr(profile_worker, "version", lambda _: "worker-test")

        monkeypatch.setattr(profile_worker, "worker_endpoint", lambda **_: next(pending))

        monkeypatch.setattr(profile_worker, "WindowsProcessScope", lambda: self.scope)

        monkeypatch.setattr(profile_worker, "WorkerAuthorizationServer", lambda **_: self.authorization)

    def open(self, *, worker_script: Path | None = None) -> ProfileWorkerProcess:

        self.scope.worker_script = worker_script

        return ProfileWorkerProcess(self.identity, storage_root=self.root, worker_script=worker_script)


def retained_cleanup_error(error: BaseException) -> AsyncResourceCleanupError:

    cleanup = error.__dict__.get("async_cleanup_error")

    assert isinstance(cleanup, AsyncResourceCleanupError)

    return cleanup


def control_request(channel: Channel, identity: ProfileWorkerIdentity) -> ProfileWorkerRequest:
    """Decode the actual emitted request through the canonical frame reader."""

    reader = Channel(identity)

    reader.inbound = bytearray(b"".join(channel.writes))

    channel.writes.clear()

    return read_document(reader, ProfileWorkerRequest, deadline=time.monotonic() + 5)


def control_reply(
    channel: Channel, reply: ProfileWorkerStatus | ProfileWorkerHumanOutcome | ProfileWorkerRefusal
) -> None:
    """Queue actual canonical reply bytes at the explicit native channel port."""

    write_document(channel, reply, deadline=time.monotonic() + 5)

    channel.inbound.extend(b"".join(channel.writes))

    channel.writes.clear()
