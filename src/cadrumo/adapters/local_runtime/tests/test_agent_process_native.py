"""The agent host's controller against real contained process trees on Windows."""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import threading
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.application.agent_host.controller import (
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
    ResolvedAgentCredentials,
)
from cadrumo.application.agent_host.credential_frame import AgentCredential, build_credential_frame
from cadrumo.application.agent_host.launcher_protocol import AgentLauncherRefusal, launcher_refusal_for
from cadrumo.application.agent_host.native_refusal import NativeLaunchRefusal, NativeLaunchRefusalCode

from ..agent_process import WindowsAgentProcessLauncher
from . import agent_host_fixture
from .process_support import fixture_arguments, fixture_environment, native_python

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows Job containment"),
]

_FIXTURE = "cadrumo.adapters.local_runtime.tests.agent_host_fixture"
_FAKE = b"sk-test-NOT-A-REAL-KEY"
_GATEWAY_FAKE = b"zai-test-NOT-A-REAL-KEY"
_ZAI_URL = "https://api.z.ai/api/anthropic"
_CONTROLLER_LOGGER = "cadrumo.application.agent_host.controller"


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
    tmp_path: Path, mode: str, source: _CredentialSource, *, ready_timeout: float = 30
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
            stop_grace=10,
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


def test_a_key_change_after_start_withdraws_the_published_agent(tmp_path: Path) -> None:
    source = _CredentialSource()
    controller = _controller(tmp_path, "ready", source)
    controller.start()
    try:
        source.generations = AgentGenerations(sign_in="login-1", provider_settings="settings-2")
        assert controller.published() is None
        assert controller.state is AgentHostState.DETACHED
    finally:
        controller.stop()


def test_an_agent_speaking_another_hosting_contract_is_not_published(tmp_path: Path) -> None:
    controller = _controller(tmp_path, "future", _CredentialSource())
    with pytest.raises(AgentHostError) as refused:
        controller.start()
    assert refused.value.reason is AgentHostRefusal.NOT_READY
    assert controller.state is AgentHostState.DETACHED


def test_the_agent_job_admits_no_breakaway_and_knows_its_own_members(tmp_path: Path) -> None:
    import os

    import win32job

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
        breakaway = win32job.JOB_OBJECT_LIMIT_BREAKAWAY_OK | win32job.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
        flags = process.job_limit_flags()
        assert flags & breakaway == 0
        assert flags & win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
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
