"""The agent host's controller against real contained process trees on Windows."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override

import pytest

from cadrumo.tests.hang_guard import HANG_GUARD_SECONDS, eventually
from cadrumo.tests.log_records import delivered_records
from cadrumo.tests.process_support import fixture_arguments, fixture_environment, native_python
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline, TimeoutPolicy
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...host.controller import (
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
    AgentProcess,
    AgentReady,
    ResolvedAgentCredentials,
)
from ...host.credential_frame import AgentCredential, build_credential_frame
from ...host.launch_environment import HOSTED_ROOT_VARIABLE
from ...host.launcher_protocol import AgentLauncherRefusal, launcher_refusal_for
from ...host.native_refusal import NativeLaunchRefusal, NativeLaunchRefusalCode
from ...host.store_lifecycle import InvocationCancellation
from ...service import AgentService
from ..agent_process import WindowsAgentInvocationRunner, WindowsAgentProcessLauncher
from . import agent_host_fixture

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows Job containment"),
]

_FIXTURE = "cadrumo_agent_service.adapters.tests.agent_host_fixture"
_FAKE = b"sk-test-NOT-A-REAL-KEY"
_GATEWAY_FAKE = b"zai-test-NOT-A-REAL-KEY"
_ZAI_URL = "https://api.z.ai/api/anthropic"
_CONTROLLER_LOGGER = "cadrumo_agent_service.host.controller"
_RETIREMENT_LOGGER = "cadrumo_agent_service.host.controller.retirement"


class _CredentialSource:
    """The signed-in profile's resolver, reduced to fixed values and a movable generation."""

    def __init__(self) -> None:
        self.generations = AgentGenerations(sign_in="login-1", provider_settings="settings-1")
        self.handed_out: list[AgentCredential] = []
        self.on_resolve: list[AgentGenerations] = []

    def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
        credentials: Mapping[str, AgentCredential] = {
            "anthropic": AgentCredential(bytearray(_FAKE)),
            "zai": AgentCredential(bytearray(_GATEWAY_FAKE), _ZAI_URL),
        }
        self.handed_out.extend(credentials.values())
        resolved = ResolvedAgentCredentials(generations=self.generations, credentials=credentials)
        if self.on_resolve:
            self.generations = self.on_resolve.pop()
        return resolved

    def current_generations(self, *, deadline: TimeoutDeadline | None = None) -> AgentGenerations | None:
        return self.generations


def _controller(tmp_path: Path, mode: str, source: _CredentialSource, *, timeout: float = 30) -> AgentHostController:
    return AgentHostController(
        launcher=WindowsAgentProcessLauncher(),
        credentials=source,
        launch=AgentLaunch(
            executable=native_python(),
            arguments=fixture_arguments(_FIXTURE, mode, str(tmp_path)),
            directory=tmp_path,
            environment=fixture_environment(),
            timeout_policy=TimeoutPolicy(timeout),
        ),
    )


def _received(tmp_path: Path) -> dict[str, object]:
    received: object = json.loads((tmp_path / "received.json").read_text(encoding="utf-8"))
    assert isinstance(received, dict)
    return {str(key): value for key, value in received.items()}


def _alive(pid: int, *, within: float = 0) -> bool:
    """Whether the process still runs after up to ``within`` seconds of waiting for it to end.

    A job's accounting reaches zero as its members end; each process object is
    signalled a moment later, so a check for death waits within a short bound.
    """
    import pywintypes
    import win32api
    import win32event

    try:
        handle = win32api.OpenProcess(0x100000, False, pid)
    except pywintypes.error:
        return False
    try:
        return win32event.WaitForSingleObject(handle, int(within * 1000)) == win32event.WAIT_TIMEOUT
    finally:
        win32api.CloseHandle(handle)


def test_the_agent_receives_its_keys_only_on_standard_input_and_stops_with_its_whole_tree(tmp_path: Path) -> None:
    source = _CredentialSource()
    controller = _controller(tmp_path, "ready", source)
    ready = controller.start()
    try:
        assert controller.state is AgentHostState.READY
        assert ready.gateway_port == 47001 and ready.hosting_contract == 1
        assert controller.published() == ready
        received = _received(tmp_path)
        expected = build_credential_frame(
            {"anthropic": AgentCredential(bytearray(_FAKE)), "zai": AgentCredential(bytearray(_GATEWAY_FAKE), _ZAI_URL)}
        )
        assert received["frame_sha256"] == hashlib.sha256(expected).hexdigest()
        assert received["providers"] == ["anthropic", "zai"]
        exposed = json.dumps({"environment": received["environment"], "arguments": received["arguments"]})
        assert _FAKE.decode() not in exposed and _GATEWAY_FAKE.decode() not in exposed
        # The controller's own copies are wiped once the frame is written.
        assert all(credential.secret == bytearray() for credential in source.handed_out)
        grandchild = received["grandchild"]
        assert isinstance(grandchild, int) and _alive(grandchild)
    finally:
        controller.stop()
    assert controller.state is AgentHostState.DETACHED
    assert (tmp_path / "stopped").read_text(encoding="utf-8") == "stdin closed"
    assert not _alive(grandchild, within=5)
    assert controller.published() is None


def test_an_agent_refusal_is_typed_and_leaves_no_process(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "refuse", _CredentialSource())
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    assert refused.value.reason is AgentHostRefusal.AGENT_REFUSED
    assert refused.value.agent_code == "provider_unsupported"
    assert controller.state is AgentHostState.DETACHED


@pytest.mark.parametrize("invalid_frame", [False, True], ids=["resolution-refused", "invalid-frame"])
def test_imports_can_run_during_resolution_but_failed_credentials_retire_the_waiting_process(
    tmp_path: Path, invalid_frame: bool
) -> None:
    observed_pids: list[int] = []

    class WaitingCredentials(_CredentialSource):
        @override
        def resolve_for_agent(self, *, deadline: TimeoutDeadline | None = None) -> ResolvedAgentCredentials:
            # A real child must reach its input gate while resolution is still
            # in progress. No frame or ready publication can precede it.
            marker = tmp_path / "awaiting-frame"
            marker_deadline = time.monotonic() + 30
            while not marker.exists():
                assert time.monotonic() < marker_deadline, "gateway did not start beside credential resolution"
                time.sleep(0.05)
            pid = int(marker.read_text(encoding="utf-8"))
            observed_pids.append(pid)
            assert _alive(pid)
            assert not (tmp_path / "received.json").exists()
            assert controller.published() is None
            if not invalid_frame:
                raise AgentHostError(AgentHostRefusal.SIGNED_OUT)
            resolved = super().resolve_for_agent()
            self.handed_out[0].secret.append(0)
            return resolved

    source = WaitingCredentials()
    controller = _controller(tmp_path, "await_credentials", source)
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    expected = AgentHostRefusal.CREDENTIALS_INVALID if invalid_frame else AgentHostRefusal.SIGNED_OUT
    assert refused.value.reason is expected
    assert controller.state is AgentHostState.DETACHED
    assert controller.published() is None
    assert observed_pids and all(not _alive(pid, within=5) for pid in observed_pids)
    assert not (tmp_path / "received.json").exists()
    assert all(credential.secret == bytearray() for credential in source.handed_out)


def test_an_agent_that_never_answers_is_ended_at_the_timeout(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "silent", _CredentialSource(), timeout=3)
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    assert refused.value.reason is AgentHostRefusal.TIMEOUT
    assert controller.state is AgentHostState.DETACHED


def test_a_sign_out_while_starting_retires_the_tree_instead_of_publishing_it(tmp_path: Path) -> None:
    source = _CredentialSource()
    source.on_resolve.append(AgentGenerations(sign_in="login-2", provider_settings="settings-1"))
    controller = _controller(tmp_path, "ready", source)
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    assert refused.value.reason is AgentHostRefusal.STALE_GENERATION
    assert controller.state is AgentHostState.DETACHED
    grandchild = _received(tmp_path)["grandchild"]
    assert isinstance(grandchild, int) and not _alive(grandchild, within=5)


def test_a_key_change_after_start_withdraws_the_published_agent_and_leaves_its_retirement_to_the_owner(
    tmp_path: Path,
) -> None:
    source = _CredentialSource()
    controller = _controller(tmp_path, "ready", source)
    controller.start()
    grandchild = _received(tmp_path)["grandchild"]
    assert isinstance(grandchild, int)
    try:
        assert not controller.superseded()
        source.generations = AgentGenerations(sign_in="login-1", provider_settings="settings-2")
        started = time.monotonic()
        assert controller.published() is None
        # Reading the published agent neither waits on the tree nor ends it.
        assert time.monotonic() - started < 1
        assert controller.superseded()
        assert controller.state is AgentHostState.READY
        assert _alive(grandchild)
    finally:
        controller.stop()
    assert controller.state is AgentHostState.DETACHED
    assert not controller.superseded()
    assert not _alive(grandchild, within=5)


def test_an_agent_speaking_another_hosting_contract_is_not_published(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "future", _CredentialSource())
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    assert refused.value.reason is AgentHostRefusal.NOT_READY
    assert controller.state is AgentHostState.DETACHED


def test_the_agent_job_knows_its_own_members(tmp_path: Path) -> None:
    import os

    from ..agent_process import WindowsAgentProcess

    process = WindowsAgentProcessLauncher().launch(
        executable=native_python(),
        arguments=fixture_arguments(_FIXTURE, "ready", str(tmp_path)),
        directory=tmp_path,
        environment=fixture_environment(),
    )
    assert isinstance(process, WindowsAgentProcess)
    try:
        process.write_input(build_credential_frame({"anthropic": AgentCredential(bytearray(_FAKE))}))
        process.read_output_line(limit=4096, timeout=30)
        grandchild = _received(tmp_path)["grandchild"]
        assert isinstance(grandchild, int)
        # A descendant of the agent is a member; this test process is not.
        assert process.contains_process_id(grandchild)
        assert not process.contains_process_id(os.getpid())
    finally:
        process.close_input()
        process.terminate(timeout=10)


def _refused(tmp_path: Path, mode: str) -> tuple[AgentHostController, AgentHostError]:
    controller = _controller(tmp_path, mode, _CredentialSource(), timeout=30)
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    return controller, refused.value


def test_an_exit_with_the_native_hosts_status_is_its_typed_refusal_with_its_code_and_subject(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_CONTROLLER_LOGGER):
        controller, error = _refused(tmp_path, "native_refusal")
    assert error.reason is AgentHostRefusal.LAUNCH_PROFILE_REFUSED
    assert error.native_refusal == NativeLaunchRefusal(
        code=NativeLaunchRefusalCode.LAUNCH_VALUE_MALFORMED, subject=agent_host_fixture.NATIVE_REFUSAL_SUBJECT
    )
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_FAILED
    assert controller.state is AgentHostState.DETACHED
    assert not (tmp_path / "received.json").exists()
    messages = [record.getMessage() for record in delivered_records(caplog) if record.name == _CONTROLLER_LOGGER]
    assert messages == [
        "agent launch refused by the native host exit=125 native_refusal=launch_value_malformed "
        f"subject={agent_host_fixture.NATIVE_REFUSAL_SUBJECT}"
    ]
    # Only the host's own last line is read: the other line it wrote is never logged.
    assert agent_host_fixture.NATIVE_NOISE_LINE.decode().strip() not in " ".join(messages)


def test_a_last_line_that_is_not_the_hosts_is_a_refusal_without_a_code_and_none_of_it_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_CONTROLLER_LOGGER):
        controller, error = _refused(tmp_path, "native_unreadable")
    assert error.reason is AgentHostRefusal.LAUNCH_PROFILE_REFUSED
    assert error.native_refusal == NativeLaunchRefusal(code=None, subject=None)
    assert controller.state is AgentHostState.DETACHED
    assert "S3CRET" not in " ".join(record.getMessage() for record in delivered_records(caplog))


def test_the_hosts_line_without_the_hosts_status_is_only_a_failed_launch(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger=_CONTROLLER_LOGGER):
        controller, error = _refused(tmp_path, "native_other_exit")
    # Whether the frame or the missing ready line is met first depends on how fast the tree ends.
    assert error.reason in {AgentHostRefusal.LAUNCH_FAILED, AgentHostRefusal.NOT_READY}
    assert error.native_refusal is None
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_FAILED
    assert controller.state is AgentHostState.DETACHED
    assert [record for record in delivered_records(caplog) if record.name == _CONTROLLER_LOGGER] == []


def test_an_agent_that_fills_its_standard_error_is_not_blocked_and_its_drain_ends_with_its_tree(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path, "chatty", _CredentialSource(), timeout=30)
    ready = controller.start()
    try:
        assert ready.gateway_port == 47001
        assert controller.state is AgentHostState.READY
    finally:
        controller.stop()
    assert not [thread for thread in threading.enumerate() if thread.name == "agent-standard-error"]


def test_a_tree_that_ignores_stop_is_ended_only_at_timeout(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A sleeping tree is allowed to finish until the injected timeout."""
    controller = _controller(tmp_path, "deaf", _CredentialSource(), timeout=3)
    controller.start()
    grandchild = _received(tmp_path)["grandchild"]
    assert isinstance(grandchild, int)
    try:
        with caplog.at_level(logging.INFO, logger=_RETIREMENT_LOGGER):
            started = time.monotonic()
            controller.stop()
            elapsed = time.monotonic() - started
    finally:
        controller.stop()
    assert controller.state is AgentHostState.DETACHED
    assert 3.0 <= elapsed < 8.0, f"the stop took {elapsed:.3f} s"
    assert not _alive(grandchild, within=5)
    retired = [record.getMessage() for record in delivered_records(caplog) if record.name == _RETIREMENT_LOGGER]
    assert len(retired) == 1
    assert retired[0].startswith("agent tree retired: stop timeout after ")


def test_a_tree_that_exits_on_the_stop_is_ended_as_soon_as_it_has(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    controller = _controller(tmp_path, "ready", _CredentialSource())
    controller.start()
    with caplog.at_level(logging.INFO, logger=_RETIREMENT_LOGGER):
        started = time.monotonic()
        controller.stop()
        elapsed = time.monotonic() - started
    assert (tmp_path / "stopped").read_text(encoding="utf-8") == "stdin closed"
    assert elapsed < 5.0, f"the stop took {elapsed:.3f} s"
    retired = [record.getMessage() for record in delivered_records(caplog) if record.name == _RETIREMENT_LOGGER]
    assert len(retired) == 1
    assert retired[0].startswith("agent tree retired: stop exited after ")


def test_gateway_and_worker_logs_from_contained_processes_join_application_feed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Exercise the real job and pipe drain with a separate worker PID whose records the agent relays."""
    hosted_root = str(tmp_path / "agent")
    environment = dict(fixture_environment())
    environment[HOSTED_ROOT_VARIABLE] = hosted_root
    caplog.set_level(logging.DEBUG)
    process = WindowsAgentProcessLauncher().launch(
        executable=native_python(),
        arguments=fixture_arguments(_FIXTURE, "diagnostics", str(tmp_path), hosted_root),
        directory=tmp_path,
        environment=environment,
    )
    try:
        process.write_input(bytearray(b"{}\n"))
        assert b"agent_ready" in process.read_output_line(limit=4096, timeout=30)
        eventually(
            lambda: any(r.msg == "worker relayed probe" for r in delivered_records(caplog)),
            what="the relayed worker record reaching the log",
        )
    finally:
        process.terminate(timeout=10)
    gateway = [r for r in delivered_records(caplog) if r.msg == "gateway live probe"]
    worker = [r for r in delivered_records(caplog) if r.msg == "worker relayed probe"]
    assert len(gateway) == len(worker) == 1
    assert gateway[0].levelno == logging.DEBUG
    assert worker[0].levelno == logging.ERROR
    assert gateway[0].process != worker[0].process
    assert gateway[0].__dict__["_cadrumo_process_role"] == "extension_service"
    assert worker[0].__dict__["_cadrumo_process_role"] == "extension_service"


@pytest.mark.parametrize("cancel_with", ["controller_cancel", "controller_stop", "service_close"])
def test_cancel_wakes_readiness_and_startup_owner_retires_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_with: str
) -> None:
    waiting = threading.Event()
    controller = _controller(tmp_path, "waiting_ready", _CredentialSource(), timeout=120)
    launch = controller._launcher.launch

    def observed_launch(
        *, executable: Path, arguments: Sequence[str], directory: Path, environment: Mapping[str, str]
    ) -> AgentProcess:
        process = launch(executable=executable, arguments=arguments, directory=directory, environment=environment)
        read = process.read_output_line

        def observed_read(*, limit: int, timeout: float) -> bytes:
            waiting.set()
            return read(limit=limit, timeout=timeout)

        monkeypatch.setattr(process, "read_output_line", observed_read)
        return process

    monkeypatch.setattr(controller._launcher, "launch", observed_launch)
    service = AgentService(
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=None, connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path / "storage",
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=lambda event: None,
    )
    service._controller = controller
    errors: list[AgentHostError] = []

    def start() -> None:
        try:
            with service._guard:
                controller.start()
        except AgentHostError as error:
            errors.append(error)

    owner = threading.Thread(target=start)
    owner.start()
    try:
        assert waiting.wait(HANG_GUARD_SECONDS), "the real child must reach its readiness wait before cancellation"
        if cancel_with == "service_close":
            service.request_close()
        elif cancel_with == "controller_stop":
            controller.stop()
        else:
            controller.cancel_start()
        owner.join(HANG_GUARD_SECONDS)
        assert not owner.is_alive(), "cancel must wake readiness without waiting for its timeout"
        assert [error.reason for error in errors] == [AgentHostRefusal.CANCELLED]
        assert controller.state is AgentHostState.DETACHED
        assert controller.published() is None
    finally:
        controller.cancel_start()
        owner.join(HANG_GUARD_SECONDS)
        if not owner.is_alive():
            service.close()


@pytest.mark.parametrize("cancel_with", ["close", "stop"])
def test_service_cancel_before_controller_exists_wakes_its_contained_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancel_with: str
) -> None:
    cancellation = InvocationCancellation()
    waiting = threading.Event()
    subscribe = cancellation.subscribe

    def subscribed(notify: Callable[[], None]) -> Callable[[], None]:
        release = subscribe(notify)
        waiting.set()
        return release

    monkeypatch.setattr(cancellation, "subscribe", subscribed)
    service = AgentService(
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=object(), connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path / "storage",
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=lambda event: None,
    )
    service._startup_cancellation = cancellation
    runner = WindowsAgentInvocationRunner(cancellation=cancellation)
    service._preparation_runner = runner
    errors: list[AgentHostError] = []

    def prepare() -> None:
        try:
            with service._guard:
                runner.run(
                    executable=native_python(),
                    arguments=fixture_arguments(_FIXTURE, "silent", str(tmp_path)),
                    directory=tmp_path,
                    environment=fixture_environment(),
                    timeout=120,
                    output_limit=4096,
                )
        except AgentHostError as error:
            errors.append(error)

    owner = threading.Thread(target=prepare)
    owner.start()
    try:
        assert waiting.wait(10)
        assert service._controller is None
        if cancel_with == "close":
            service.request_close()
        else:
            service._admit_stop()
        owner.join(10)
        assert not owner.is_alive()
        assert [error.reason for error in errors] == [AgentHostRefusal.CANCELLED]
        assert runner.settled
    finally:
        cancellation.cancel()
        owner.join(10)
        if not owner.is_alive():
            service.close()


def test_contained_preparation_reports_timeout_and_confirms_termination(tmp_path: Path) -> None:
    runner = WindowsAgentInvocationRunner()
    result = runner.run(
        executable=native_python(),
        arguments=fixture_arguments(_FIXTURE, "silent", str(tmp_path)),
        directory=tmp_path,
        environment=fixture_environment(),
        timeout=1.0,
        output_limit=4096,
    )
    assert result.status is None
    assert result.standard_output == b""
    assert runner.settled


@pytest.mark.parametrize("cancel", [False, True])
def test_service_close_wakes_a_pending_served_catalogue_body(tmp_path: Path, cancel: bool) -> None:
    reading = threading.Event()
    release = threading.Event()
    document = {"api_version": "v1", "providers": []}
    body = json.dumps(document).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.flush()
            reading.set()
            if release.wait(120):
                with contextlib.suppress(OSError):
                    self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    server_owner = threading.Thread(target=server.serve_forever)
    server_owner.start()
    service = AgentService(
        client=cast(
            InstalledServiceClient, SimpleNamespace(lease=None, connection=SimpleNamespace(close=lambda: None))
        ),
        storage_root=tmp_path / "storage",
        gateway_bearer=bytearray(b"synthetic-bearer"),
        emit=lambda event: None,
    )
    ready = AgentReady(AgentGenerations("session", "settings"), server.server_port, "test", 1)
    service._controller = cast(
        AgentHostController,
        SimpleNamespace(
            published=lambda: ready,
            cancel_start=lambda: None,
            stop=lambda: None,
        ),
    )
    errors: list[AgentHostError] = []
    results: list[dict[str, object]] = []

    def read() -> None:
        try:
            results.append(service._served_catalog(ready))
        except AgentHostError as error:
            errors.append(error)

    owner = threading.Thread(target=read)
    owner.start()
    try:
        assert reading.wait(10)
        if cancel:
            service.request_close()
        else:
            release.set()
        owner.join(10)
        assert not owner.is_alive()
        assert [error.reason for error in errors] == ([AgentHostRefusal.CANCELLED] if cancel else [])
        assert results == ([] if cancel else [document])
    finally:
        release.set()
        owner.join(10)
        service.close()
        server.shutdown()
        server_owner.join(10)
        server.server_close()
