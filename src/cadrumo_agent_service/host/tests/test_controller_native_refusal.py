"""A tree that ends before its ready line is a typed refusal; the native host's own refusal is told apart.

The controller's decisions are driven here by the exit status and standard-error
tail a tree reports, in each order its pipes can fail. The real processes,
their pipes and the runtime door are exercised by the Windows integration tests.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import cast, override
from uuid import uuid4

import pytest

from cadrumo.tests.log_records import delivered_records
from cadrumo_client.contracts import deadline_budget
from cadrumo_client.contracts.contracts import ClientHello, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.contracts.profile_access import SessionRequest
from cadrumo_client.transport.frame_io import DOCUMENT_FRAME_KIND, read_frame_payload, write_document
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.service_client import InstalledServiceClient
from cadrumo_client.transport.tests.memory_channel import MemoryChannel

from ... import service_startup as service_module
from ...gateway_credentials import GatewayCredentials
from ...service import AgentService
from ..controller import (
    EXIT_OBSERVATION_SECONDS,
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
    AgentReady,
    ResolvedAgentCredentials,
)
from ..credential_frame import AgentCredential
from ..launcher_protocol import AgentLauncherRefusal, launcher_refusal_for
from ..native_refusal import NativeLaunchRefusal, NativeLaunchRefusalCode
from ..store_lifecycle import InvocationCancellation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NATIVE_STATUS = 125
_CONTROLLER_LOGGER = "cadrumo_agent_service.host.controller"
_HOST_LINE = json.dumps({"native_refusal": "launch_value_missing", "subject": "SLOT_NAME"}).encode() + b"\n"


class _Process:
    """A tree's ports reduced to scripted outcomes; it records how it was asked."""

    def __init__(
        self,
        *,
        write_error: Exception | None = None,
        read_error: Exception | None = None,
        status: int | None = _NATIVE_STATUS,
        wait_error: Exception | None = None,
        standard_error: bytes = _HOST_LINE,
        standard_error_error: Exception | None = None,
    ) -> None:
        self._write_error = write_error
        self._read_error = read_error
        self._status = status
        self._wait_error = wait_error
        self._standard_error = standard_error
        self._standard_error_error = standard_error_error
        self.waits: list[float] = []
        self.standard_error_reads = 0
        self.terminated = False

    def write_input(self, data: bytearray) -> None:
        if self._write_error is not None:
            raise self._write_error

    def read_output_line(self, *, limit: int, timeout: float) -> bytes:
        assert self._read_error is not None, "the scripted tree answers nothing"
        raise self._read_error

    def cancel_output_wait(self) -> None:
        pass

    def settled_standard_error(self, *, timeout: float) -> bytes:
        self.standard_error_reads += 1
        if self._standard_error_error is not None:
            raise self._standard_error_error
        return self._standard_error

    def close_input(self) -> None:
        pass

    def wait(self, *, timeout: float) -> int | None:
        self.waits.append(timeout)
        if self._wait_error is not None:
            # Only the first observation fails: the controller's own retirement waits afterwards.
            error, self._wait_error = self._wait_error, None
            raise error
        if self._status is None:
            time.sleep(timeout)
        return self._status

    def terminate(self, *, timeout: float) -> None:
        self.terminated = True

    def work_done(self) -> tuple[int, ...] | None:
        # A scripted tree does no work, so a stop it does not answer is taken as ignored.
        return ()

    def contains_process_id(self, process_id: int) -> bool:
        return False


class _Launcher:
    def __init__(self, process: _Process) -> None:
        self._process = process

    def launch(
        self, *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> _Process:
        return self._process


class _Credentials:
    generations = AgentGenerations(sign_in="login-1", provider_settings="settings-1")

    def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(
            generations=self.generations,
            credentials={"example": AgentCredential(bytearray(b"sk-test-NOT-A-REAL-KEY"))},
        )

    def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations | None:
        return self.generations


def _start(process: _Process, tmp_path: Path) -> tuple[AgentHostController, AgentHostError]:
    controller = AgentHostController(
        launcher=_Launcher(process),
        credentials=_Credentials(),
        launch=AgentLaunch(executable=tmp_path / "agent", arguments=(), directory=tmp_path, environment={}),
    )
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    return controller, refused.value


def test_an_exit_with_the_hosts_status_after_the_output_ended_is_its_refusal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    process = _Process(read_error=EOFError())
    with caplog.at_level(logging.WARNING, logger=_CONTROLLER_LOGGER):
        controller, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.LAUNCH_PROFILE_REFUSED
    assert error.native_refusal == NativeLaunchRefusal(
        code=NativeLaunchRefusalCode.LAUNCH_VALUE_MISSING, subject="SLOT_NAME"
    )
    assert str(error) == "launch_profile_refused:launch_value_missing"
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_FAILED
    assert process.waits[0] == EXIT_OBSERVATION_SECONDS
    # The failed start leaves no tree behind.
    assert process.terminated and controller.state is AgentHostState.DETACHED
    messages = [record.getMessage() for record in delivered_records(caplog) if record.name == _CONTROLLER_LOGGER]
    assert messages == [
        "agent launch refused by the native host exit=125 native_refusal=launch_value_missing subject=SLOT_NAME"
    ]


def test_an_exit_with_the_hosts_status_before_the_frame_is_written_is_its_refusal(tmp_path: Path) -> None:
    process = _Process(write_error=BrokenPipeError())
    controller, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.LAUNCH_PROFILE_REFUSED
    assert error.native_refusal is not None
    assert error.native_refusal.code is NativeLaunchRefusalCode.LAUNCH_VALUE_MISSING
    assert process.terminated and controller.state is AgentHostState.DETACHED


def test_the_hosts_status_without_a_readable_line_is_still_a_launch_profile_refusal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    garbage = b"the host said S3CRET-VALUE-IN-PLAIN-TEXT in free text\n"
    with caplog.at_level(logging.WARNING, logger=_CONTROLLER_LOGGER):
        _, error = _start(_Process(read_error=EOFError(), standard_error=garbage), tmp_path)
    assert error.reason is AgentHostRefusal.LAUNCH_PROFILE_REFUSED
    assert error.native_refusal == NativeLaunchRefusal(code=None, subject=None)
    assert str(error) == "launch_profile_refused"
    logged = " ".join(record.getMessage() for record in delivered_records(caplog))
    assert "native_refusal=unrecognized subject=unrecognized" in logged
    assert "S3CRET" not in logged


def test_a_standard_error_that_cannot_be_read_still_reports_the_status(tmp_path: Path) -> None:
    process = _Process(read_error=EOFError(), standard_error_error=OSError("pipe gone"))
    _, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.LAUNCH_PROFILE_REFUSED
    assert error.native_refusal == NativeLaunchRefusal(code=None, subject=None)


def test_no_value_the_line_carries_beyond_the_closed_fields_reaches_the_error_or_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    planted = json.dumps(
        {"native_refusal": "launch_value_malformed", "subject": "SLOT_NAME", "value": "PLANTED-SECRET"}
    ).encode()
    with caplog.at_level(logging.DEBUG, logger=_CONTROLLER_LOGGER):
        _, error = _start(_Process(read_error=EOFError(), standard_error=planted + b"\n"), tmp_path)
    assert error.native_refusal == NativeLaunchRefusal(code=None, subject=None)
    everything = " ".join([str(error), *(record.getMessage() for record in delivered_records(caplog))])
    assert "PLANTED-SECRET" not in everything


def test_a_subject_that_is_a_path_is_not_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    line = json.dumps({"native_refusal": "launch_value_malformed", "subject": "C:\\Users\\someone\\agent.txt"})
    with caplog.at_level(logging.DEBUG, logger=_CONTROLLER_LOGGER):
        _, error = _start(_Process(read_error=EOFError(), standard_error=line.encode() + b"\n"), tmp_path)
    assert error.native_refusal == NativeLaunchRefusal(
        code=NativeLaunchRefusalCode.LAUNCH_VALUE_MALFORMED, subject=None
    )
    assert "someone" not in " ".join(record.getMessage() for record in delivered_records(caplog))


@pytest.mark.parametrize("status", [0, 1, 2, 64, 120, 124, 126, 0xC0000005])
def test_any_other_exit_status_is_not_the_hosts_refusal_and_its_standard_error_is_never_read(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, status: int
) -> None:
    # The standard error even holds a line shaped like the host's: only the host's status makes it one.
    process = _Process(read_error=EOFError(), status=status)
    with caplog.at_level(logging.DEBUG, logger=_CONTROLLER_LOGGER):
        controller, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.NOT_READY
    assert error.native_refusal is None
    assert process.standard_error_reads == 0
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_FAILED
    assert [record for record in delivered_records(caplog) if record.name == _CONTROLLER_LOGGER] == []
    assert process.terminated and controller.state is AgentHostState.DETACHED


def test_a_write_that_fails_for_any_other_status_stays_a_launch_failure(tmp_path: Path) -> None:
    _, error = _start(_Process(write_error=BrokenPipeError(), status=1), tmp_path)
    assert error.reason is AgentHostRefusal.LAUNCH_FAILED
    assert error.native_refusal is None


def test_a_tree_still_running_at_the_timeout_is_not_waited_for(tmp_path: Path) -> None:
    process = _Process(read_error=TimeoutError(), status=None)
    controller, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.TIMEOUT
    assert process.waits == []
    assert process.standard_error_reads == 0
    assert process.terminated and controller.state is AgentHostState.DETACHED


def test_timeout_remains_distinct_even_if_the_host_has_exited(tmp_path: Path) -> None:
    _, error = _start(_Process(read_error=TimeoutError()), tmp_path)
    assert error.reason is AgentHostRefusal.TIMEOUT


def test_a_status_that_cannot_be_observed_leaves_the_plain_refusal(tmp_path: Path) -> None:
    process = _Process(read_error=EOFError(), wait_error=RuntimeError("no handle"))
    _, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.NOT_READY
    assert process.standard_error_reads == 0


def test_cancellation_invalidates_a_ready_line_already_being_delivered(tmp_path: Path) -> None:
    class LateReady(_Process):
        @override
        def read_output_line(self, *, limit: int, timeout: float) -> bytes:
            controller.cancel_start()
            return b'{"event":"agent_ready","gateway_port":47001,"agent_version":"test","hosting_contract":1}\n'

    process = LateReady(status=0)
    controller = AgentHostController(
        launcher=_Launcher(process),
        credentials=_Credentials(),
        launch=AgentLaunch(executable=tmp_path / "agent", arguments=(), directory=tmp_path, environment={}),
    )
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    assert refused.value.reason is AgentHostRefusal.CANCELLED
    assert controller.published() is None
    assert process.terminated


@pytest.mark.parametrize("outcome", ["observation_error", "cancel", "stale", "expired", "published_stop"])
def test_post_ready_observation_and_cleanup_share_the_startup_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    now = [100.0]
    monkeypatch.setattr(deadline_budget.time, "monotonic", lambda: now[0])

    class ReadyProcess(_Process):
        @override
        def read_output_line(self, *, limit: int, timeout: float) -> bytes:
            assert timeout == 10.0
            now[0] = 106.0
            return b'{"event":"agent_ready","gateway_port":47001,"agent_version":"test","hosting_contract":1}\n'

    class ObservedCredentials(_Credentials):
        @override
        def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations | None:
            now[0] = 111.0 if outcome == "expired" else 107.0
            if outcome == "observation_error":
                raise RuntimeError("observation unavailable")
            if outcome == "cancel":
                controller.cancel_start()
            if outcome == "stale":
                return AgentGenerations(sign_in="login-2", provider_settings="settings-1")
            return self.generations

    process = ReadyProcess(status=0)
    controller = AgentHostController(
        launcher=_Launcher(process),
        credentials=ObservedCredentials(),
        launch=AgentLaunch(
            executable=tmp_path / "agent",
            arguments=(),
            directory=tmp_path,
            environment={},
            timeout_policy=deadline_budget.TimeoutPolicy(10.0),
        ),
    )
    if outcome == "published_stop":
        controller.start()
        assert controller.state is AgentHostState.READY
        now[0] = 150.0
        controller.stop()
        assert process.waits == [10.0], "an explicit stop of a published agent owns a new timeout"
    else:
        expected_error = RuntimeError if outcome == "observation_error" else AgentHostError
        with pytest.raises(expected_error) as refused:
            controller.start()
        if isinstance(refused.value, AgentHostError):
            assert (
                refused.value.reason
                is {
                    "cancel": AgentHostRefusal.CANCELLED,
                    "stale": AgentHostRefusal.STALE_GENERATION,
                    "expired": AgentHostRefusal.TIMEOUT,
                }[outcome]
            )
        assert process.waits == ([] if outcome == "expired" else [3.0])
    assert controller.state is AgentHostState.DETACHED
    assert controller.published() is None
    assert process.terminated


def test_service_replacement_retirement_consumes_the_existing_startup_deadline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [1000.0]
    monkeypatch.setattr(deadline_budget, "time", SimpleNamespace(monotonic=lambda: now[0]))
    monkeypatch.setattr(service_module, "DEFAULT_TIMEOUT_POLICY", deadline_budget.TimeoutPolicy(10.0))

    class Process(_Process):
        @override
        def wait(self, *, timeout: float) -> int | None:
            self.waits.append(timeout)
            if timeout > 0:
                now[0] += 5.0
            return 0

    class Credentials(_Credentials):
        @override
        def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations | None:
            now[0] = 1003.0
            return self.generations

    class PreparedError(RuntimeError):
        pass

    def prepared(**_arguments: object) -> None:
        raise PreparedError("replacement settled")

    process = Process(status=0)
    controller = AgentHostController(
        launcher=_Launcher(process),
        credentials=_Credentials(),
        launch=AgentLaunch(executable=tmp_path / "agent", arguments=(), directory=tmp_path, environment={}),
    )
    controller._process = process
    controller._state = AgentHostState.READY
    controller._ready = AgentReady(_Credentials.generations, 47001, "test", 1)
    service = AgentService(
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(
                lease=SimpleNamespace(profile_id=uuid4()),
                connection=SimpleNamespace(close=lambda: None),
            ),
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=lambda event: None,
    )
    service._controller = controller
    service._credentials = cast(GatewayCredentials, Credentials())
    service._owned = True
    monkeypatch.setattr(service_module, "profile_agent_workspace", lambda root: root)
    monkeypatch.setattr(service_module, "agent_image", prepared)
    try:
        with pytest.raises(PreparedError):
            service.start()
        assert process.waits == [0, 7.0]
        assert now[0] == 1008.0
        assert process.terminated
        assert controller.state is AgentHostState.DETACHED
    finally:
        service.close()


def test_startup_cancellation_closes_the_exact_credential_connection_and_never_publishes(tmp_path: Path) -> None:
    server, channel = MemoryChannel(), MemoryChannel()
    server.pair(channel)
    deadline = deadline_budget.DEFAULT_TIMEOUT_POLICY.deadline()
    write_document(
        server,
        ServerHello(product_version="cancel-test", storage_identity="a" * 64, boot_id=uuid4()),
        deadline=deadline.instant,
    )
    connection = VerifiedConnection(
        channel,
        expected=ClientHello(product_version="cancel-test", storage_identity="a" * 64),
        deadline=deadline.instant,
    )
    read_frame_payload(server, kind=DOCUMENT_FRAME_KIND, deadline=deadline.instant)
    cancellation = InvocationCancellation()

    class Credentials(_Credentials):
        @override
        def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
            assert deadline is not None
            connection.session(
                SessionRequest(action="session_status", request_id=uuid4(), profile_id=uuid4(), session_id=uuid4()),
                deadline=deadline.instant,
            )
            raise AssertionError("the held credential read must never publish a reply")

    class Process(_Process):
        @override
        def cancel_output_wait(self) -> None:
            pass

    process = Process(status=0)
    credentials = GatewayCredentials(
        Credentials(),
        bytearray(b"synthetic-bearer"),
        bytearray(b"synthetic-host"),
        Event(),
        startup_cancellation=lambda: cancellation,
        close_read=connection.close,
    )
    controller = AgentHostController(
        launcher=_Launcher(process),
        credentials=credentials,
        launch=AgentLaunch(executable=tmp_path / "agent", arguments=(), directory=tmp_path, environment={}),
    )
    release = cancellation.subscribe(controller.cancel_start)
    errors: list[AgentHostError] = []
    cancelled = Event()

    def start() -> None:
        try:
            controller.start(deadline=deadline)
        except AgentHostError as error:
            errors.append(error)

    def cancel() -> None:
        cancellation.cancel()
        cancelled.set()

    owner = Thread(target=start)
    closer = Thread(target=cancel)
    owner.start()
    try:
        read_frame_payload(server, kind=DOCUMENT_FRAME_KIND, deadline=time.monotonic() + 5)
        closer.start()
        assert cancelled.wait(2), "cancellation must not acquire the held credential exchange"
        owner.join(5)
        assert not owner.is_alive()
        assert [error.reason for error in errors] == [AgentHostRefusal.CANCELLED]
        assert controller.state is AgentHostState.DETACHED
        assert controller.published() is None
        assert process.terminated and connection.closed
    finally:
        server.close()
        owner.join(5)
        if closer.ident is not None:
            closer.join(5)
        release()
        connection.close()


@pytest.mark.parametrize("background_stop", [False, True])
def test_unconfirmed_retirement_never_reports_that_a_timeout_stopped_the_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    background_stop: bool,
) -> None:
    events: list[dict[str, object]] = []
    service = AgentService(
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=None, connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=events.append,
    )
    unresolved = cast(AgentHostController, SimpleNamespace(state=AgentHostState.STOPPING))

    def failed(*_arguments: object, **_keywords: object) -> None:
        service._controller = unresolved
        raise RefusalError(RefusalCode.TIMEOUT)

    try:
        if background_stop:
            monkeypatch.setattr(service, "stop", failed)
            service._background_stop()
            assert events == [{"event": "refused", "code": "agent_service_failed"}]
        else:
            monkeypatch.setattr(service, "_start_owned", failed)
            with pytest.raises(AgentHostError) as refused:
                service.start()
            assert refused.value.reason is AgentHostRefusal.STORES_UNPREPARED
        assert service._controller is unresolved
    finally:
        service._controller = None
        monkeypatch.undo()
        service.close()
