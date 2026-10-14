"""A tree that ends before its ready line is a typed refusal; the native host's own refusal is told apart.

The controller's decisions are driven here by the exit status and standard-error
tail a tree reports, in each order its pipes can fail. The real processes,
their pipes and the runtime door are exercised by the Windows integration tests.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from ..controller import (
    EXIT_OBSERVATION_SECONDS,
    AgentGenerations,
    AgentHostController,
    AgentHostError,
    AgentHostRefusal,
    AgentHostState,
    AgentLaunch,
    ResolvedAgentCredentials,
)
from ..credential_frame import AgentCredential
from ..launcher_protocol import AgentLauncherRefusal, launcher_refusal_for
from ..native_refusal import NativeLaunchRefusal, NativeLaunchRefusalCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NATIVE_STATUS = 125
_CONTROLLER_LOGGER = "cadrumo.application.agent_host.controller"
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
        return self._status

    def terminate(self, *, timeout: float) -> None:
        self.terminated = True

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

    def resolve_for_agent(self) -> ResolvedAgentCredentials:
        return ResolvedAgentCredentials(
            generations=self.generations,
            credentials={"example": AgentCredential(bytearray(b"sk-test-NOT-A-REAL-KEY"))},
        )

    def current_generations(self) -> AgentGenerations | None:
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
    messages = [record.getMessage() for record in caplog.records if record.name == _CONTROLLER_LOGGER]
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
    logged = " ".join(record.getMessage() for record in caplog.records)
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
    everything = " ".join([str(error), *(record.getMessage() for record in caplog.records)])
    assert "PLANTED-SECRET" not in everything


def test_a_subject_that_is_a_path_is_not_logged(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    line = json.dumps({"native_refusal": "launch_value_malformed", "subject": "C:\\Users\\someone\\agent.txt"})
    with caplog.at_level(logging.DEBUG, logger=_CONTROLLER_LOGGER):
        _, error = _start(_Process(read_error=EOFError(), standard_error=line.encode() + b"\n"), tmp_path)
    assert error.native_refusal == NativeLaunchRefusal(
        code=NativeLaunchRefusalCode.LAUNCH_VALUE_MALFORMED, subject=None
    )
    assert "someone" not in " ".join(record.getMessage() for record in caplog.records)


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
    assert [record for record in caplog.records if record.name == _CONTROLLER_LOGGER] == []
    assert process.terminated and controller.state is AgentHostState.DETACHED


def test_a_write_that_fails_for_any_other_status_stays_a_launch_failure(tmp_path: Path) -> None:
    _, error = _start(_Process(write_error=BrokenPipeError(), status=1), tmp_path)
    assert error.reason is AgentHostRefusal.LAUNCH_FAILED
    assert error.native_refusal is None


def test_a_tree_still_running_at_the_ready_bound_is_not_waited_for(tmp_path: Path) -> None:
    process = _Process(read_error=TimeoutError(), status=None)
    controller, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.NOT_READY
    assert process.waits[0] == 0.0
    assert process.standard_error_reads == 0
    assert process.terminated and controller.state is AgentHostState.DETACHED


def test_a_tree_that_exited_with_the_hosts_status_by_the_ready_bound_is_its_refusal(tmp_path: Path) -> None:
    _, error = _start(_Process(read_error=TimeoutError()), tmp_path)
    assert error.reason is AgentHostRefusal.LAUNCH_PROFILE_REFUSED


def test_a_status_that_cannot_be_observed_leaves_the_plain_refusal(tmp_path: Path) -> None:
    process = _Process(read_error=EOFError(), wait_error=RuntimeError("no handle"))
    _, error = _start(process, tmp_path)
    assert error.reason is AgentHostRefusal.NOT_READY
    assert process.standard_error_reads == 0
