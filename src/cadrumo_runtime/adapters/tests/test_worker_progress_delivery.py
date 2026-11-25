"""A failed native cue signal retries over a fresh verified worker connection."""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from threading import Event
from typing import NoReturn, override
from uuid import UUID, uuid4

import pytest

from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.access_contracts import (
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    ProfileAccessBinding,
)
from cadrumo.core.operations import OperationFrontendProjection
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.contracts import Peer
from cadrumo_client.contracts.login import LoginInventory
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.windows_process import WindowsProcessScope
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationRequest,
    WorkerModelRun,
)
from cadrumo_runtime.host.profile_connection import ProfileConnection
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections

from ..worker_authorization import WorkerAuthorizationServer
from ..worker_transport import WorkerChannel
from .profile_worker_support import owner_id
from .worker_authority_support import UnavailableApprovalAuthority
from .worker_progress_delivery_fixture import ProgressResult, ProgressSeed, wait_for_marker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows worker containment"),
]


class _Login:
    login_id = "synthetic-progress-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


class _CueOwner(UnavailableApprovalAuthority):
    def __init__(self, profiles: RuntimeProfileConnections, profile_id: UUID) -> None:
        self.profiles = profiles
        self.profile_id = profile_id
        self.publications: list[tuple[int, bool]] = []
        self.completed: list[int] = []

    def authorize(self, request: WorkerAuthorityRequest) -> NoReturn:
        raise AssertionError("progress must not execute an authorized operation")

    def model_run(self, authority: WorkerAuthorizationRequest, command: WorkerModelRun, body: bytearray) -> NoReturn:
        raise AssertionError("progress must not run a model")

    def operations_advanced(
        self,
        operation_ids: tuple[OperationId, ...],
        *,
        records_changed: bool = False,
        settled: tuple[OperationId, ...] = (),
    ) -> None:
        self.publications.append((time.perf_counter_ns(), records_changed))
        self.profiles._operations_advanced(self.profile_id, operation_ids, records_changed)
        self.completed.append(time.perf_counter_ns())


class _CountingServer(WorkerAuthorizationServer):
    accepted = 0

    @override
    def _verify_worker_channel(self, channel: WorkerChannel) -> None:
        super()._verify_worker_channel(channel)
        self.accepted += 1


@pytest.mark.parametrize("records_changed", [False, True])
def test_native_signal_failure_retries_partial_fanout_without_duplicate_cues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, records_changed: bool, caplog: pytest.LogCaptureFixture
) -> None:
    import win32api
    import win32event

    timing_logger = "cadrumo_runtime.application.operation_cue_timing"
    caplog.set_level(logging.DEBUG, logger=timing_logger)

    identity = ProfileWorkerIdentity(
        worker_id=uuid4(),
        runtime_boot_id=uuid4(),
        binding=ProfileAccessBinding(
            profile_id=uuid4(), installation_id=uuid4(), os_owner_id=owner_id(), custody_generation=1, dek_epoch=uuid4()
        ),
    )
    seed = ProgressSeed(identity=identity, parent_pid=os.getpid(), records_changed=records_changed)
    (tmp_path / "seed.json").write_text(seed.model_dump_json(), encoding="utf-8")
    login = _Login()
    profiles = RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=identity.runtime_boot_id,
        stop=Event(),
        service_descriptors=(),
        login_inventory=lambda: LoginInventory(logins=(login,), complete=True),
    )
    contexts: list[ConnectionContext] = []
    wakes: list[NativeWake] = []
    for _ in range(3):
        context = ConnectionContext(
            uuid4(), identity.runtime_boot_id, Peer(os_owner_id=owner_id(), process_id=os.getpid())
        )
        wake = NativeWake()
        session_id = uuid4()
        profiles.connect_events(context, queued=wake)
        profiles._connections[context.connection_id] = ProfileConnection(
            context=context,
            login=login,
            client_id=uuid4(),
            profile_id=identity.binding.profile_id,
            frontend=OperationFrontendProjection.DESKTOP,
            session_id=session_id,
        )
        profiles._operation_watches[context.connection_id] = {"c" * 64: session_id}
        contexts.append(context)
        wakes.append(wake)
    signal = win32event.SetEvent
    failures: list[int] = []

    def fail_once(handle: int) -> None:
        if int(handle) == wakes[1].waitable and not failures:
            failures.append(time.perf_counter_ns())
            raise OSError("synthetic native signal failure")
        signal(handle)

    monkeypatch.setattr(win32event, "SetEvent", fail_once)
    scope = WindowsProcessScope()
    servers: list[_CountingServer] = []
    process_handles: list[int] = []
    owner = _CueOwner(profiles, identity.binding.profile_id)
    contained = Event()

    def contain() -> None:
        contained.set()
        scope.terminate()

    try:
        scope.launch(
            executable=Path(sys.executable),
            arguments=("-I", "-m", "cadrumo_runtime.adapters.tests.worker_progress_delivery_fixture", str(tmp_path)),
            directory=tmp_path,
            environment=os.environ.copy(),
        )
        wait_for_marker(tmp_path / "worker.pid")
        pid = int((tmp_path / "worker.pid").read_text(encoding="ascii"))
        process_handle = win32api.OpenProcess(0x100000 | 0x1000, False, pid)
        process_handles.append(process_handle)
        server = _CountingServer(
            identity=identity,
            root=tmp_path,
            process_id=pid,
            owns_process=lambda pid: pid in scope.active_process_ids(),
            contain=contain,
            owner=owner,
        )
        servers.append(server)
        (tmp_path / "listening").write_text("1", encoding="ascii")
        wait_for_marker(tmp_path / "acknowledged")
        expected = ["profile_records_changed", "operation_changed"] if records_changed else ["operation_changed"]
        for context, wake in zip(contexts, wakes, strict=True):
            assert wake.is_set()
            assert win32event.WaitForSingleObject(wake.waitable, 0) == win32event.WAIT_OBJECT_0
            events = profiles.take_events(context)
            assert [event.kind for event in events] == expected
            assert all(event.connection_id == context.connection_id for event in events)
        (tmp_path / "finish").write_text("1", encoding="ascii")
        wait_for_marker(tmp_path / "result.json")
        result = ProgressResult.model_validate_json((tmp_path / "result.json").read_bytes())
        assert [mark.stage for mark in result.marks] == ["commit", "send", "refused", "send", "ack"]
        assert len(failures) == 1
        assert len(owner.publications) == 2
        assert [changed for _, changed in owner.publications] == [records_changed, records_changed]
        assert len(owner.completed) == 1
        assert failures[0] < result.marks[2].ticks < result.marks[3].ticks <= owner.completed[0] < result.marks[4].ticks
        assert result.opened == server.accepted == 2
        assert not contained.is_set()
        server.require_healthy()
        assert win32event.WaitForSingleObject(process_handle, 10_000) == win32event.WAIT_OBJECT_0
    finally:
        for server in servers:
            server.close()
        scope.terminate()
        for server in servers:
            server.settle()
        for process_handle in process_handles:
            win32api.CloseHandle(process_handle)
    messages = [record.getMessage() for record in caplog.records if record.name == timing_logger]
    stages = [message.split("stage=", 1)[1].split(" ", 1)[0] for message in messages]
    assert stages == [
        "parent_received",
        "fanout_start",
        "parent_received",
        "fanout_start",
        "publish_cues_complete",
        "parent_ack_written",
    ]
    assert all(str(identity.binding.profile_id) not in message for message in messages)
    completed = next(message for message in messages if "stage=publish_cues_complete " in message)
    assert completed.endswith(f"cue_attempt_count={6 if records_changed else 3}")
