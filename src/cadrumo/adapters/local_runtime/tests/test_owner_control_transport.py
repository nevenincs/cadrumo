"""Real local sockets/pipes isolate global owner consent from profile channels."""

from __future__ import annotations

import sys
import tempfile
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimeClientHello,
    RuntimeRefusalCode,
    RuntimeRefusalError,
    RuntimeShutdownIncompleteError,
)
from cadrumo.application.runtime.owner_control import (
    RuntimeStopAccepted,
    RuntimeStopConfirm,
    RuntimeStopPreview,
    RuntimeStopPreviewRequest,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileLogin
from cadrumo.application.runtime.transport import RuntimeStatusRequest, RuntimeTransportStatus
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext

from ..framing import VerifiedRuntimeConnection
from ..posix import PosixRuntimeEndpoint
from ..server import RuntimeTransportServer
from ..windows import WindowsRuntimeEndpoint

pytestmark = [pytest.mark.integration, pytest.mark.hex_inbound_adapter]


@dataclass
class NativeLoginObservation:
    """Synthetic login state; the actual transport still verifies the native peer."""

    owner: str
    login_id: str = "synthetic-owner-login"
    locked: bool = False

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.owner,
            active=True,
            locked=self.locked,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@dataclass
class RunningOwnerServer:
    host: RuntimeTransportServer
    endpoint: PosixRuntimeEndpoint | WindowsRuntimeEndpoint
    serving: Future[None]
    observations: list[NativeLoginObservation]
    preparation_calls: list[bool] = field(default_factory=list)
    clients: list[VerifiedRuntimeConnection] = field(default_factory=list)
    finalization_calls: list[bool] = field(default_factory=list)
    finalization_completed: list[bool] = field(default_factory=list)
    finalization_entered: Event = field(default_factory=Event)
    finalization_refuse: Event = field(default_factory=Event)
    finalization_release: Event = field(default_factory=Event)
    lifecycle_events: list[str] = field(default_factory=list)
    namespace: Path | None = None

    def connect(self) -> VerifiedRuntimeConnection:
        client = VerifiedRuntimeConnection(
            self.endpoint.connect(timeout=3),
            expected=RuntimeClientHello(product_version="owner-test", storage_identity=self.endpoint.storage_identity),
            deadline=time.monotonic() + 3,
        )
        self.clients.append(client)
        return client

    def competing_endpoint(self, *, storage_root: Path) -> PosixRuntimeEndpoint | WindowsRuntimeEndpoint:
        if isinstance(self.endpoint, WindowsRuntimeEndpoint):
            return WindowsRuntimeEndpoint(storage_root=storage_root)
        assert self.namespace is not None
        return PosixRuntimeEndpoint(storage_root=storage_root, namespace=self.namespace)


@pytest.fixture
def owner_server(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[RunningOwnerServer]:
    parent = None if sys.platform == "win32" else Path("/") / "tmp"
    with tempfile.TemporaryDirectory(prefix="cr-owner-", dir=parent) as folder:
        namespace = None if sys.platform == "win32" else Path(folder) / "ipc"
        endpoint = (
            WindowsRuntimeEndpoint(storage_root=tmp_path)
            if sys.platform == "win32"
            else PosixRuntimeEndpoint(storage_root=tmp_path, namespace=namespace)
        )
        observations: list[NativeLoginObservation] = []
        stop = Event()
        preparation_calls: list[bool] = []
        finalization_calls: list[bool] = []
        finalization_completed: list[bool] = []
        finalization_entered = Event()
        finalization_refuse = Event()
        finalization_release = Event()
        lifecycle_events: list[str] = []
        preparation = getattr(request, "param", True)
        if preparation == "finalize-refuse":
            finalization_refuse.set()

        def prepare_stop() -> None:
            preparation_calls.append(True)
            lifecycle_events.append("prepare")
            if preparation in ("refuse", "finalize-prepare-refuse"):
                raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
            if preparation == "signal":
                stop.set()
                # The serving loop observes stop before this confirming
                # thread can send acceptance, as with native manager SIGTERM.
                time.sleep(0.4)

        def finalize_stop() -> None:
            finalization_calls.append(True)
            lifecycle_events.append("finalize")
            finalization_entered.set()
            if preparation == "finalize-block" and not finalization_release.wait(6):
                raise RuntimeError("synthetic fixture finalizer was not released")
            if finalization_refuse.is_set():
                raise RuntimeError("synthetic fixture finalizer refused")
            finalization_completed.append(True)

        def capture(channel: RuntimeByteChannel) -> NativeLoginObservation:
            observation = NativeLoginObservation(channel.peer.os_owner_id)
            observations.append(observation)
            return observation

        host = RuntimeTransportServer(
            endpoint,
            product_version="owner-test",
            stop=stop,
            capture_owner_login=capture,
            owner_stop_available=preparation is not False,
            prepare_owner_stop=prepare_stop if isinstance(preparation, str) else None,
            finalize_owner_stop=(
                finalize_stop
                if preparation in ("finalize-block", "finalize-refuse", "finalize-prepare-refuse")
                else None
            ),
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            serving = pool.submit(host.serve)
            running = RunningOwnerServer(
                host,
                endpoint,
                serving,
                observations,
                preparation_calls,
                finalization_calls=finalization_calls,
                finalization_completed=finalization_completed,
                finalization_entered=finalization_entered,
                finalization_refuse=finalization_refuse,
                finalization_release=finalization_release,
                lifecycle_events=lifecycle_events,
                namespace=namespace,
            )
            try:
                assert host.ready.wait(3)
                yield running
            finally:
                for client in running.clients:
                    client.close()
                host.stop.set()
                try:
                    serving.result(timeout=7)
                except RuntimeShutdownIncompleteError:
                    if preparation != "finalize-refuse":
                        raise
                    if not host._listener_owner.released:
                        finalization_refuse.clear()
                        try:
                            host.retry_drain(deadline=time.monotonic() + 3)
                        except RuntimeShutdownIncompleteError:
                            host._listener_owner.close_now()


def _preview(client: VerifiedRuntimeConnection) -> RuntimeStopPreview:
    result = client.owner_control(RuntimeStopPreviewRequest(request_id=uuid4()), deadline=time.monotonic() + 3)
    assert isinstance(result, RuntimeStopPreview)
    return result


def _confirm(preview: RuntimeStopPreview) -> RuntimeStopConfirm:
    return RuntimeStopConfirm(
        request_id=uuid4(),
        runtime_boot_id=preview.runtime_boot_id,
        preview_id=preview.preview_id,
        acknowledge_all_profiles_and_work=True,
    )


def _assert_same_storage_owner_busy(owner_server: RunningOwnerServer, storage_root: Path) -> None:
    contender = owner_server.competing_endpoint(storage_root=storage_root)
    try:
        with pytest.raises(RuntimeRefusalError) as refusal:
            contender.listen()
        assert refusal.value.reason is RuntimeRefusalCode.OWNER_BUSY
    finally:
        contender.close()


def _assert_same_storage_listener_available(owner_server: RunningOwnerServer, storage_root: Path) -> None:
    contender = owner_server.competing_endpoint(storage_root=storage_root)
    try:
        contender.listen()
    finally:
        contender.close()


def test_owner_disconnect_preserves_other_clients_and_confirm_drains_native_host(
    owner_server: RunningOwnerServer,
) -> None:
    observer = owner_server.connect()
    abandoned = owner_server.connect()
    _preview(abandoned)
    abandoned.close()
    assert observer.status(
        RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 3
    ).accepting_connections
    owner = owner_server.connect()
    preview = _preview(owner)
    result = owner.owner_control(_confirm(preview), deadline=time.monotonic() + 3)
    assert isinstance(result, RuntimeStopAccepted)
    assert result.runtime_boot_id == owner_server.host.identity.boot_id
    owner_server.serving.result(timeout=7)
    assert not owner_server.host.ready.is_set()


def test_profile_proof_and_global_owner_control_cannot_share_a_connection(owner_server: RunningOwnerServer) -> None:
    profile = owner_server.connect()
    secret = bytearray(b"never-sent-synthetic-proof")
    refused = profile.login(
        RuntimeProfileLogin(
            request_id=uuid4(), profile_id=uuid4(), method="api_key", frontend=OperationFrontendProjection.MCP
        ),
        secret,
        deadline=time.monotonic() + 3,
    )
    assert isinstance(refused, RuntimeAccessRefusal)
    assert secret == bytearray(len(secret))
    refused_owner = profile.owner_control(RuntimeStopPreviewRequest(request_id=uuid4()), deadline=time.monotonic() + 3)
    assert isinstance(refused_owner, RuntimeAccessRefusal)
    assert refused_owner.code is RuntimeRefusalCode.PEER_UNTRUSTED
    assert owner_server.observations == []
    owner = owner_server.connect()
    _preview(owner)
    refused_profile = owner.login(
        RuntimeProfileLogin(
            request_id=uuid4(), profile_id=uuid4(), method="password", frontend=OperationFrontendProjection.CLI
        ),
        bytearray(b"never-sent-other-synthetic-proof"),
        deadline=time.monotonic() + 3,
    )
    assert isinstance(refused_profile, RuntimeAccessRefusal)
    assert refused_profile.code is RuntimeRefusalCode.PEER_UNTRUSTED
    assert not owner_server.host.stop.is_set()


def test_native_owner_channel_rechecks_lock_and_does_not_resurrect_consumed_consent(
    owner_server: RunningOwnerServer,
) -> None:
    owner = owner_server.connect()
    preview = _preview(owner)
    owner_server.observations[0].locked = True
    refused = owner.owner_control(_confirm(preview), deadline=time.monotonic() + 3)
    assert isinstance(refused, RuntimeAccessRefusal)
    assert refused.code is RuntimeRefusalCode.PEER_UNTRUSTED
    owner_server.observations[0].locked = False
    replay = owner.owner_control(_confirm(preview), deadline=time.monotonic() + 3)
    assert isinstance(replay, RuntimeAccessRefusal)
    assert replay.code is RuntimeRefusalCode.INVALID_FRAME
    assert not owner_server.host.stop.is_set()


def test_copied_native_preview_cannot_stop_from_another_connection(owner_server: RunningOwnerServer) -> None:
    original, copied = owner_server.connect(), owner_server.connect()
    preview = _preview(original)
    refused = copied.owner_control(_confirm(preview), deadline=time.monotonic() + 3)
    assert isinstance(refused, RuntimeAccessRefusal)
    assert refused.code is RuntimeRefusalCode.INVALID_FRAME
    assert not owner_server.host.stop.is_set()


@pytest.mark.parametrize("owner_server", [False], indirect=True)
def test_unavailable_managed_stop_refuses_before_native_login_or_drain(owner_server: RunningOwnerServer) -> None:
    owner = owner_server.connect()
    refused = owner.owner_control(RuntimeStopPreviewRequest(request_id=uuid4()), deadline=time.monotonic() + 3)
    assert isinstance(refused, RuntimeAccessRefusal)
    assert refused.code is RuntimeRefusalCode.UNAVAILABLE
    assert owner_server.observations == []
    assert not owner_server.host.stop.is_set()
    assert owner.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 3).accepting_connections


@pytest.mark.parametrize("owner_server", ["finalize-prepare-refuse"], indirect=True)
def test_native_preparation_requires_valid_consent_and_refusal_preserves_runtime(
    owner_server: RunningOwnerServer,
) -> None:
    owner = owner_server.connect()
    preview = _preview(owner)
    assert owner_server.preparation_calls == []
    copied = _confirm(preview).model_copy(update={"preview_id": uuid4()})
    invalid = owner.owner_control(copied, deadline=time.monotonic() + 3)
    assert isinstance(invalid, RuntimeAccessRefusal) and invalid.code is RuntimeRefusalCode.INVALID_FRAME
    assert owner_server.preparation_calls == []
    refused = owner.owner_control(_confirm(_preview(owner)), deadline=time.monotonic() + 3)
    assert isinstance(refused, RuntimeAccessRefusal) and refused.code is RuntimeRefusalCode.VERSION_MISMATCH
    assert owner_server.preparation_calls == [True]
    assert owner_server.lifecycle_events == ["prepare"]
    assert owner_server.finalization_calls == []
    status = owner.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 3)
    assert isinstance(status, RuntimeTransportStatus) and status.accepting_connections
    assert not owner_server.host.stop.is_set()


@pytest.mark.parametrize("owner_server", ["finalize-block"], indirect=True)
def test_accepted_owner_stop_finalizes_after_drain_before_releasing_singleton(
    owner_server: RunningOwnerServer, tmp_path: Path
) -> None:
    owner = owner_server.connect()
    reply = owner.owner_control(_confirm(_preview(owner)), deadline=time.monotonic() + 3)
    assert isinstance(reply, RuntimeStopAccepted)
    assert owner_server.preparation_calls == [True]
    assert owner_server.finalization_entered.wait(3)
    assert owner_server.lifecycle_events == ["prepare", "finalize"]
    assert owner_server.finalization_calls == [True]
    assert not owner_server.serving.done()
    with pytest.raises(RuntimeRefusalError) as drained:
        owner.status(RuntimeStatusRequest(request_id=uuid4()), deadline=time.monotonic() + 2)
    assert drained.value.reason is RuntimeRefusalCode.CONNECTION_CLOSED
    _assert_same_storage_owner_busy(owner_server, tmp_path)
    assert not owner_server.serving.done()

    owner_server.finalization_release.set()
    owner_server.serving.result(timeout=7)
    assert not owner_server.host.ready.is_set()
    _assert_same_storage_listener_available(owner_server, tmp_path)


@pytest.mark.parametrize("owner_server", ["finalize-refuse"], indirect=True)
def test_owner_finalizer_refusal_retains_singleton_until_owned_fixture_cleanup(
    owner_server: RunningOwnerServer, tmp_path: Path
) -> None:
    owner = owner_server.connect()
    reply = owner.owner_control(_confirm(_preview(owner)), deadline=time.monotonic() + 3)
    assert isinstance(reply, RuntimeStopAccepted)
    assert owner_server.finalization_entered.wait(3)
    assert owner_server.lifecycle_events == ["prepare", "finalize"]
    assert owner_server.finalization_calls == [True]
    assert owner_server.finalization_completed == []
    with pytest.raises(RuntimeShutdownIncompleteError):
        owner_server.serving.result(timeout=7)
    _assert_same_storage_owner_busy(owner_server, tmp_path)
    with pytest.raises(RuntimeShutdownIncompleteError):
        owner_server.host.retry_drain(deadline=time.monotonic() + 3)
    assert owner_server.finalization_calls == [True, True]
    assert owner_server.finalization_completed == []
    _assert_same_storage_owner_busy(owner_server, tmp_path)

    owner_server.finalization_refuse.clear()
    owner_server.host.retry_drain(deadline=time.monotonic() + 3)
    assert owner_server.finalization_calls == [True, True, True]
    assert owner_server.finalization_completed == [True]
    _assert_same_storage_listener_available(owner_server, tmp_path)
    owner_server.host.retry_drain(deadline=time.monotonic() + 3)
    assert owner_server.finalization_calls == [True, True, True]


@pytest.mark.parametrize("owner_server", ["signal"], indirect=True)
def test_native_stop_during_preparation_preserves_bounded_acceptance_write(owner_server: RunningOwnerServer) -> None:
    owner = owner_server.connect()
    reply = owner.owner_control(_confirm(_preview(owner)), deadline=time.monotonic() + 3)
    assert isinstance(reply, RuntimeStopAccepted)
    assert owner_server.preparation_calls == [True]
    owner_server.serving.result(timeout=7)
    assert not owner_server.host.ready.is_set()
