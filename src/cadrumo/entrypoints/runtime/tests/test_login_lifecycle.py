"""Trusted login inventory fences private work and reuses native runtime drain."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.runtime.contracts import RuntimeExitReason
from cadrumo.application.runtime.login import RuntimeLoginInventory
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileStatus, RuntimeSessionRequest
from cadrumo.application.user_profile.access_contracts import LoginEligibility, OsLockState
from cadrumo.core.config import override_settings

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from .. import main
from ..arguments import parse_runtime_arguments
from ..profile_connections import RuntimeProfileConnections
from .test_profile_connections import LoginObservation, connect, login

pytestmark = [pytest.mark.hex_entrypoint]


@pytest.mark.unit
@pytest.mark.parametrize("complete", [pytest.param(False, id="unknown"), pytest.param(True, id="proven-absence")])
def test_inventory_absence_drains_only_after_verified_eligibility(tmp_path: Path, complete: bool) -> None:
    stop = Event()
    native = LoginObservation("synthetic-owner")
    current = RuntimeLoginInventory((), complete=False)
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="synthetic-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
        login_inventory=lambda: current,
    )
    # A public-only runtime has not experienced an eligible login/logout.
    assert profiles._login_contexts() == ()
    assert not profiles._private_work_available() and not stop.is_set()
    assert current.eligibility is LoginEligibility.UNKNOWN
    current = RuntimeLoginInventory((), complete=True)
    profiles._login_contexts()
    assert not profiles._private_work_available() and not stop.is_set()
    current = RuntimeLoginInventory((native,), complete=True)
    assert profiles._login_contexts() == (native,)
    assert profiles._private_work_available()
    native.lock_state = OsLockState.LOCKED
    current = RuntimeLoginInventory((native,), complete=False)
    profiles._login_contexts()
    assert profiles._private_work_available() and not stop.is_set()
    native.active = False
    current = RuntimeLoginInventory((), complete=complete)
    profiles._login_contexts()
    assert stop.is_set() and not profiles._private_work_available()
    expected = LoginEligibility.INELIGIBLE if complete else LoginEligibility.UNKNOWN
    assert current.complete is complete and current.eligibility is expected
    native.active = True
    current = RuntimeLoginInventory((native,), complete=True)
    profiles._login_contexts()
    assert not profiles._private_work_available()


@pytest.mark.unit
def test_stale_inventory_witness_cannot_retain_custody_after_fresh_observation_loss(tmp_path: Path) -> None:
    stop = Event()
    native = LoginObservation("synthetic-owner")
    current = RuntimeLoginInventory((native,), complete=False)
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="synthetic-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
        login_inventory=lambda: current,
    )
    assert profiles._login_contexts() == (native,)
    assert profiles._private_work_available() and not stop.is_set()
    native.active = False
    # Enumeration's positive entry survives; only its fresh native observation
    # establishes whether this incarnation still permits private work.
    assert current.eligibility is LoginEligibility.ELIGIBLE
    assert profiles._login_contexts() == (native,)
    assert stop.is_set() and not profiles._private_work_available()
    assert current.eligibility is LoginEligibility.ELIGIBLE and current.complete is False


@pytest.mark.unit
def test_peer_witness_survives_incomplete_enumeration_and_keeps_original_object(tmp_path: Path) -> None:
    stop = Event()
    original = LoginObservation("synthetic-owner", login_id="original-incarnation")
    duplicate = LoginObservation("synthetic-owner", login_id=original.login_id)
    current = RuntimeLoginInventory((duplicate,), complete=False)
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="synthetic-storage",
        runtime_boot_id=uuid4(),
        stop=stop,
        login_inventory=lambda: current,
    )
    profiles._logins[original.login_id] = original
    observed = profiles._login_contexts()
    assert len(observed) == 1 and observed[0] is original
    current = RuntimeLoginInventory((), complete=False)
    assert profiles._login_contexts()[0] is original
    assert profiles._private_work_available() and not stop.is_set()
    original.active = False
    other = LoginObservation("synthetic-owner", login_id="other-incarnation")
    current = RuntimeLoginInventory((other,), complete=False)
    profiles._login_contexts()
    assert profiles._private_work_available() and not stop.is_set()
    other.active = False
    current = RuntimeLoginInventory((), complete=False)
    profiles._login_contexts()
    assert stop.is_set() and not profiles._private_work_available()
    assert current.eligibility is LoginEligibility.UNKNOWN


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows transport and owned workers")
@pytest.mark.usefixtures("authority_operation")
@pytest.mark.parametrize("complete", [pytest.param(False, id="unknown"), pytest.param(True, id="proven-absence")])
def test_login_witness_loss_drains_real_worker_without_revoking_grants(tmp_path: Path, complete: bool) -> None:
    """Login/store observations are explicit ports; encrypted custody and Jobs are real."""
    import win32api
    import win32con
    import win32event

    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        enrollment_id = uuid4()
        subject.service.request(enrollment_id, subject.proposal)
        subject.approve(enrollment_id)
        record = subject.store.enrollment_state().requests[0]
        secret = subject.owner.delivery.endpoint.possession(record)
        assert secret is not None
        profile = subject.store.binding.profile_id
        close_active_bucket_session()
        stop, boot = Event(), uuid4()
        original = LoginObservation(owner_id(), login_id="synthetic-original-login")
        other = LoginObservation(owner_id(), login_id="synthetic-other-login")
        current = RuntimeLoginInventory((original,), complete=True)
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: original,
            login_inventory=lambda: current,
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version="test", stop=stop, profiles=profiles, boot_id=boot
        )
        clients = []
        native_handles: list[int] = []
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                api, human = connect(endpoint), connect(endpoint)
                clients.extend((api, human))
                admitted = login(api, profile, "api_key", secret.get_secret_value())
                assert isinstance(admitted, RuntimeProfileStatus) and admitted.status.denial is None
                api_id = admitted.status.session_id
                assert api_id is not None
                from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT

                human_admitted = login(human, profile, "password", PROFILE_INPUT.encode())
                assert isinstance(human_admitted, RuntimeProfileStatus) and human_admitted.status.denial is None
                human_id = human_admitted.status.session_id
                assert human_id is not None
                host = profiles._profiles[profile]
                worker = host.owner._worker
                assert worker is not None
                process = worker._process
                assert isinstance(process, WindowsOwnedProcess) and process._handle is not None
                process_handle = win32api.DuplicateHandle(
                    win32api.GetCurrentProcess(),
                    process._handle,
                    win32api.GetCurrentProcess(),
                    0,
                    False,
                    win32con.DUPLICATE_SAME_ACCESS,
                )
                native_handles.append(process_handle)
                before = subject.store.snapshot()
                lock_before = subject.store.profile_lock_state()
                original.active = False
                current = RuntimeLoginInventory((other,), complete=False)
                human_lost = human.session(
                    RuntimeSessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=human_id
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(human_lost, RuntimeAccessRefusal) or (
                    isinstance(human_lost, RuntimeProfileStatus) and human_lost.status.denial is not None
                )
                independent = api.session(
                    RuntimeSessionRequest(
                        action="session_status", request_id=uuid4(), profile_id=profile, session_id=api_id
                    ),
                    deadline=time.monotonic() + 5,
                )
                assert isinstance(independent, RuntimeProfileStatus) and independent.status.denial is None
                assert not stop.is_set()
                other.active = False
                current = RuntimeLoginInventory((), complete=complete)
                # Trigger the same fresh observation used at admission; the
                # server must then drain without a stronger absence claim.
                profiles._last_poll = time.monotonic() + 60
                profiles._login_contexts()
                assert stop.is_set() and not profiles._private_work_available()
                expected = LoginEligibility.INELIGIBLE if complete else LoginEligibility.UNKNOWN
                assert current.complete is complete and current.eligibility is expected
                running.result(timeout=20)
                assert stop.is_set() and not server.ready.is_set()
                assert win32event.WaitForSingleObject(process_handle, 1000) == win32event.WAIT_OBJECT_0
                after = subject.store.snapshot()
                assert after.grants == before.grants and after.keys == before.keys
                assert subject.store.profile_lock_state() == lock_before
                assert profiles.drain(deadline=time.monotonic() + 1).uncontained == ()
            finally:
                stop.set()
                for client in clients:
                    client.close()
                running.result(timeout=20)
                endpoint.close()
                for handle in native_handles:
                    win32api.CloseHandle(handle)


@pytest.mark.unit
def test_main_linux_inventory_composition_drives_real_login_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native/process ports are explicit; inventory consumption is the real owner."""
    native = LoginObservation("1000", login_id="linux-desktop-incarnation")
    current = RuntimeLoginInventory((native,), complete=True)
    inventory_owners: list[str] = []
    prepared: list[RuntimeProfileConnections] = []
    released: list[bool] = []
    signal_calls: list[tuple[int, object]] = []
    original_handlers = {2: object(), 15: object()}

    def inventory(*, expected_owner: str) -> RuntimeLoginInventory:
        inventory_owners.append(expected_owner)
        return current

    def endpoint(*, storage_root: Path) -> SimpleNamespace:
        assert storage_root == tmp_path
        return SimpleNamespace(storage_identity="unit-storage", close=lambda: released.append(True))

    def prepare_registry(profiles: RuntimeProfileConnections) -> None:
        # Isolate unrelated public graph compilation; never open private state.
        prepared.append(profiles)

    class ServerPort:
        DRAIN_SECONDS = RetainedRuntimeTransportServer.DRAIN_SECONDS

        def __init__(
            self, endpoint: object, *, profiles: RuntimeProfileConnections, stop: Event, **_options: object
        ) -> None:
            self.profiles, self.stop = profiles, stop
            assert prepared == [profiles]
            assert profiles.root == tmp_path and profiles.storage_identity == "unit-storage"

        def serve(self) -> None:
            nonlocal current
            assert isinstance(self.profiles, RuntimeProfileConnections)
            assert self.profiles._login_contexts() == (native,)
            assert self.profiles._private_work_available() and not self.stop.is_set()
            assert inventory_owners == ["1000"]
            native.active = False
            current = RuntimeLoginInventory((), complete=True)
            assert self.profiles._login_contexts() == ()
            assert self.stop.is_set() and not self.profiles._private_work_available()
            assert inventory_owners == ["1000", "1000"]

    def watchdog(stop: Event, *, timeout: float) -> AbstractContextManager[None]:
        assert not stop.is_set() and timeout == RetainedRuntimeTransportServer.DRAIN_SECONDS + 2
        return nullcontext()

    monkeypatch.setattr(main, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(main, "version", lambda _name: "unit-version")
    monkeypatch.setattr(main, "posix_owner_uid", lambda: 1000)
    monkeypatch.setattr(main, "linux_login_inventory", inventory)
    monkeypatch.setattr(main, "PosixRuntimeEndpoint", endpoint)
    monkeypatch.setattr(main, "RuntimeTransportServer", ServerPort)
    monkeypatch.setattr(main, "RuntimeShutdownWatchdog", watchdog)
    monkeypatch.setattr(RuntimeProfileConnections, "prepare_registry", prepare_registry)
    monkeypatch.setattr(
        main,
        "signal",
        SimpleNamespace(
            SIGINT=2,
            SIGTERM=15,
            getsignal=original_handlers.__getitem__,
            signal=lambda number, handler: signal_calls.append((number, handler)),
        ),
    )
    with override_settings(cadrumo_dev_runtime_session_override="0"):
        assert (
            main.run(
                parse_runtime_arguments(
                    [
                        "--storage-root",
                        str(tmp_path),
                        "--storage-identity",
                        "unit-storage",
                        "--expected-version",
                        "unit-version",
                    ]
                )
            )
            == RuntimeExitReason.LOGIN_WITNESS_LOSS
        )
    assert released == [True] and len(prepared) == 1
    assert signal_calls[-2:] == list(original_handlers.items())
