"""A contained child reached only through its private standard pipes."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from ..windows_process import WindowsProcessScope
from .process_support import fixture_arguments, fixture_environment, native_python
from .windows_inheritance_fixture import WindowsHandleProbe

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_outbound_adapter,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows Job containment"),
]

_PIPES = "cadrumo_runtime.adapters.tests.standard_pipe_fixture"
_INHERITANCE = "cadrumo_runtime.adapters.tests.windows_inheritance_fixture"


def test_a_frame_written_on_standard_input_is_answered_on_standard_output(tmp_path: Path) -> None:
    scope = WindowsProcessScope()
    try:
        child, standard_input, standard_output, standard_error = scope.launch_with_standard_pipes(
            executable=native_python(),
            arguments=fixture_arguments(_PIPES),
            directory=tmp_path,
            environment=fixture_environment(),
        )
        frame = b'{"version":1,"credentials":{"anthropic":{"secret":"sk-test-NOT-A-REAL-KEY"}}}\n'
        standard_input.write(frame)
        answer = standard_output.readline()
        assert answer == hashlib.sha256(frame).hexdigest().encode("ascii") + b"\n"
        assert child.pid in scope.active_process_ids()
        # Closing standard input is the stop signal: the child sees end of file and exits.
        standard_input.close()
        assert child.wait(timeout=10) == 0
        standard_output.close()
        standard_error.close()
    finally:
        scope.terminate()


def test_standard_error_is_a_private_pipe_the_parent_reads_apart_from_standard_output(tmp_path: Path) -> None:
    scope = WindowsProcessScope()
    try:
        child, standard_input, standard_output, standard_error = scope.launch_with_standard_pipes(
            executable=native_python(),
            arguments=fixture_arguments(_PIPES, "stderr"),
            directory=tmp_path,
            environment=fixture_environment(),
        )
        standard_input.close()
        assert child.wait(timeout=10) == 0
        # The child answered an empty frame on standard output and wrote its diagnostic only to standard error.
        assert standard_output.read() == hashlib.sha256(b"").hexdigest().encode("ascii") + b"\n"
        assert standard_error.read() == b"the child's diagnostic\n"
        standard_output.close()
        standard_error.close()
    finally:
        scope.terminate()


def test_only_the_three_pipe_ends_are_inherited(tmp_path: Path) -> None:
    import pywintypes
    import win32api
    import win32event

    attributes = pywintypes.SECURITY_ATTRIBUTES()
    attributes.bInheritHandle = True
    sentinel = win32event.CreateEvent(attributes, True, False, None)
    scope = WindowsProcessScope()
    try:
        assert win32api.GetHandleInformation(sentinel) & 1
        record = tmp_path / "contained.json"
        child, standard_input, standard_output, standard_error = scope.launch_with_standard_pipes(
            executable=native_python(),
            arguments=fixture_arguments(_INHERITANCE, "probe", str(record), str(int(sentinel))),
            directory=tmp_path,
            environment=fixture_environment(),
        )
        standard_input.close()
        assert child.wait(timeout=10) == 0
        standard_output.close()
        standard_error.close()
        absent = WindowsHandleProbe.model_validate_json(record.read_bytes())
        assert absent.process.pid == child.pid
        assert absent.handle_flags is None or absent.handle_flags & 1 == 0
        assert absent.signal_error == 6  # ERROR_INVALID_HANDLE
        assert win32event.WaitForSingleObject(sentinel, 0) == win32event.WAIT_TIMEOUT
    finally:
        try:
            scope.terminate()
        finally:
            win32api.CloseHandle(sentinel)


def test_terminating_the_scope_ends_a_child_still_waiting_on_its_pipes(tmp_path: Path) -> None:
    import win32api
    import win32event

    scope = WindowsProcessScope()
    child, standard_input, standard_output, standard_error = scope.launch_with_standard_pipes(
        executable=native_python(),
        arguments=fixture_arguments(_PIPES),
        directory=tmp_path,
        environment=fixture_environment(),
    )
    observer = win32api.OpenProcess(0x100000, False, child.pid)
    try:
        assert win32event.WaitForSingleObject(observer, 0) == win32event.WAIT_TIMEOUT
        scope.terminate(timeout=10)
        # The job's accounting reaches zero as the process ends; its own object
        # is signalled a moment later, so observe it within a short bound.
        assert win32event.WaitForSingleObject(observer, 5000) == win32event.WAIT_OBJECT_0
        assert scope.active_process_ids() == ()
    finally:
        win32api.CloseHandle(observer)
        standard_input.close()
        standard_output.close()
        standard_error.close()
