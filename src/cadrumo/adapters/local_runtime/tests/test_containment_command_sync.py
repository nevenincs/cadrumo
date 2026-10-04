"""Bounded native containment command output and process cleanup through isolated OS ports."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from .. import containment_commands
from ..containment_commands import ContainmentCommand, ContainmentCommandResult, run_containment_command_sync

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _Pipe:
    def __init__(self) -> None:
        self.closed = False

    def fileno(self) -> int:
        return 57

    def close(self) -> None:
        self.closed = True


class _Process:
    def __init__(self, *, missing_stdout: bool, wait_timeout: bool) -> None:
        self.stdout = None if missing_stdout else _Pipe()
        self.returncode: int | None = None
        self.killed = False
        self.wait_timeout = wait_timeout

    def kill(self) -> None:
        self.killed = True

    def wait(self, *, timeout: float) -> int:
        if self.wait_timeout and not self.killed:
            raise subprocess.TimeoutExpired("synthetic-manager", timeout)
        self.returncode = 0
        return 0


@pytest.mark.parametrize(
    ("payload", "unreadable", "missing_stdout", "wait_timeout", "expected", "killed"),
    [
        (b"public manager state", False, False, False, None, False),
        (b"\xff", False, False, False, RuntimeRefusalCode.INVALID_FRAME, False),
        (b"x" * (64 * 1024 + 1), False, False, False, RuntimeRefusalCode.INVALID_FRAME, True),
        (b"", True, False, False, RuntimeRefusalCode.DEADLINE_EXCEEDED, True),
        (b"", False, True, False, RuntimeRefusalCode.UNAVAILABLE, True),
        (b"", False, False, True, RuntimeRefusalCode.DEADLINE_EXCEEDED, True),
    ],
    ids=["complete", "invalid-utf8", "oversize", "read-timeout", "no-stdout", "wait-timeout"],
)
def test_sync_containment_command_output_refusal_and_owned_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    unreadable: bool,
    missing_stdout: bool,
    wait_timeout: bool,
    expected: RuntimeRefusalCode | None,
    killed: bool,
) -> None:
    process = _Process(missing_stdout=missing_stdout, wait_timeout=wait_timeout)
    chunks = iter((payload, b""))
    monkeypatch.setattr(containment_commands, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(containment_commands, "os", SimpleNamespace(getuid=lambda: 1000, read=lambda *_: next(chunks)))
    monkeypatch.setattr(
        containment_commands,
        "select",
        SimpleNamespace(select=lambda readable, *_: ((), (), ()) if unreadable else (readable, (), ())),
    )
    monkeypatch.setattr(
        containment_commands,
        "subprocess",
        SimpleNamespace(
            Popen=lambda *_args, **_kwargs: process,
            PIPE=subprocess.PIPE,
            DEVNULL=subprocess.DEVNULL,
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )

    if expected is None:
        assert run_containment_command_sync(
            ContainmentCommand.SYSTEMCTL, ("show", "synthetic.service")
        ) == ContainmentCommandResult(returncode=0, output=payload.decode("utf-8"))
    else:
        with pytest.raises(RuntimeRefusalError) as raised:
            run_containment_command_sync(ContainmentCommand.SYSTEMCTL, ("show", "synthetic.service"))
        assert raised.value.reason is expected

    assert process.killed is killed
    if process.stdout is not None:
        assert process.stdout.closed
