"""The agent host's controller against real contained process trees on Windows."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import override

import pytest

from cadrumo.tests.process_support import fixture_arguments, fixture_environment, native_python

from ...host.controller import (
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
    ResolvedAgentCredentials,
)
from ...host.credential_frame import AgentCredential, build_credential_frame
from ...host.launch_environment import HOSTED_ROOT_VARIABLE
from ...host.launcher_protocol import AgentLauncherRefusal, launcher_refusal_for
from ...host.native_refusal import NativeLaunchRefusal, NativeLaunchRefusalCode
from ..agent_process import WindowsAgentProcessLauncher
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

    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        credentials: Mapping[str, AgentCredential] = {
            "anthropic": AgentCredential(bytearray(_FAKE)),
            "zai": AgentCredential(bytearray(_GATEWAY_FAKE), _ZAI_URL),
        }
        self.handed_out.extend(credentials.values())
        resolved = ResolvedAgentCredentials(generations=self.generations, credentials=credentials)
        if self.on_resolve:
            self.generations = self.on_resolve.pop()
        return resolved

    def current_generations(self) -> AgentGenerations | None:
        return self.generations


def _controller(
    tmp_path: Path, mode: str, source: _CredentialSource, *, ready_timeout: float = 30, stop_grace: float = 10
) -> AgentHostController:
    return AgentHostController(
        launcher=WindowsAgentProcessLauncher(),
        credentials=source,
        launch=AgentLaunch(
            executable=native_python(),
            arguments=fixture_arguments(_FIXTURE, mode, str(tmp_path)),
            directory=tmp_path,
            environment=fixture_environment(),
            ready_timeout=ready_timeout,
            stop_grace=stop_grace,
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
        def resolve_for_agent(self) -> ResolvedAgentCredentials:
            # A real child must reach its input gate while resolution is still
            # in progress. No frame or ready publication can precede it.
            marker = tmp_path / "awaiting-frame"
            deadline = time.monotonic() + 30
            while not marker.exists():
                assert time.monotonic() < deadline, "gateway did not start beside credential resolution"
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


def test_an_agent_that_never_answers_is_ended_at_the_ready_bound(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "silent", _CredentialSource(), ready_timeout=3)
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    assert refused.value.reason is AgentHostRefusal.NOT_READY
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
    controller = _controller(tmp_path, mode, _CredentialSource(), ready_timeout=30)
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
    messages = [record.getMessage() for record in caplog.records if record.name == _CONTROLLER_LOGGER]
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
    assert "S3CRET" not in " ".join(record.getMessage() for record in caplog.records)


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
    assert [record for record in caplog.records if record.name == _CONTROLLER_LOGGER] == []


def test_an_agent_that_fills_its_standard_error_is_not_blocked_and_its_drain_ends_with_its_tree(
    tmp_path: Path,
) -> None:
    controller = _controller(tmp_path, "chatty", _CredentialSource(), ready_timeout=30)
    ready = controller.start()
    try:
        assert ready.gateway_port == 47001
        assert controller.state is AgentHostState.READY
    finally:
        controller.stop()
    assert not [thread for thread in threading.enumerate() if thread.name == "agent-standard-error"]


def test_a_tree_that_ignores_the_stop_is_ended_once_it_does_no_work_not_at_the_grace_period(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The agent never reads the end of its input, and its grandchild only sleeps.

    The stall bound is 1 s and the tree is sampled every 0.1 s, so the stop
    ends the tree after about 1.1 s; the 30 s grace period would never be
    reached. The bound of 5 s leaves the job's termination its loaded-host time.
    """
    controller = _controller(tmp_path, "deaf", _CredentialSource(), stop_grace=30)
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
    assert 1.0 <= elapsed < 5.0, f"the stop took {elapsed:.3f} s"
    assert not _alive(grandchild, within=5)
    retired = [record.getMessage() for record in caplog.records if record.name == _RETIREMENT_LOGGER]
    assert len(retired) == 1
    assert retired[0].startswith("agent tree retired: stop stalled after ")


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
    retired = [record.getMessage() for record in caplog.records if record.name == _RETIREMENT_LOGGER]
    assert len(retired) == 1
    assert retired[0].startswith("agent tree retired: stop exited after ")


def test_gateway_and_worker_logs_from_contained_processes_join_application_feed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Exercise the real job and pipe drain with a separate worker PID whose records the agent relays."""
    import time

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
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not any(r.msg == "worker relayed probe" for r in caplog.records):
            time.sleep(0.02)
    finally:
        process.terminate(timeout=10)
    gateway = [r for r in caplog.records if r.msg == "gateway live probe"]
    worker = [r for r in caplog.records if r.msg == "worker relayed probe"]
    assert len(gateway) == len(worker) == 1
    assert gateway[0].levelno == logging.DEBUG
    assert worker[0].levelno == logging.ERROR
    assert gateway[0].process != worker[0].process
    assert gateway[0].__dict__["_cadrumo_process_role"] == "extension_service"
    assert worker[0].__dict__["_cadrumo_process_role"] == "extension_service"
