"""Captured-call output and timeout ownership, using isolated real subprocesses."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from cadrumo_harness.mcp.call_runtime import run_captured

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("inside_event_loop", [False, True])
def test_captured_completion_preserves_streams_stdin_environment_and_exit_status(inside_event_loop: bool) -> None:
    argv = [
        sys.executable,
        "-c",
        "import os, sys; "
        "sys.stdout.write(os.environ['CAPTURE_FIXTURE'] + ':' + sys.stdin.read()); "
        "sys.stderr.write('diagnostic'); sys.exit(7)",
    ]

    def invoke() -> subprocess.CompletedProcess[str]:
        return run_captured(
            argv, timeout_s=10, stdin_payload="synthetic input", env={**os.environ, "CAPTURE_FIXTURE": "value"}
        )

    async def invoke_inside_loop() -> subprocess.CompletedProcess[str]:
        return invoke()

    result = asyncio.run(invoke_inside_loop()) if inside_event_loop else invoke()
    assert result.args == argv
    assert result.returncode == 7
    assert result.stdout == "value:synthetic input"
    assert result.stderr == "diagnostic"


@pytest.mark.skipif(sys.platform == "win32", reason="requires native POSIX sessions and process groups")
@pytest.mark.parametrize("api", ["captured", "supervised"])
@pytest.mark.parametrize("mode", ["direct", "tree", "exited"])
def test_timeout_only_targets_launch_owned_posix_group(tmp_path: Path, api: str, mode: str) -> None:
    asyncio.run(_isolated_timeout(tmp_path, api, mode))


async def _isolated_timeout(tmp_path: Path, api: str, mode: str) -> None:
    if sys.platform == "win32":
        raise RuntimeError("timeout regression requires native POSIX isolation")
    fixture = Path(__file__).with_name("subprocess_cleanup_fixture.py")
    subject = await asyncio.create_subprocess_exec(
        sys.executable,
        str(fixture),
        "subject",
        str(tmp_path),
        mode,
        api,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    isolated = False
    try:
        assert subject.stdout is not None
        assert await asyncio.wait_for(subject.stdout.readline(), timeout=10) == b"ready\n"
        # No timeout call is enabled until the outer runner proves isolation.
        assert os.getpgid(subject.pid) == subject.pid
        assert os.getsid(subject.pid) == subject.pid
        assert subject.pid != os.getpgrp()
        isolated = True
        stdout, stderr = await asyncio.wait_for(subject.communicate(b"go\n"), timeout=30)
        assert subject.returncode == 0, (subject.returncode, stdout, stderr)
        assert stdout == b"timeout verified; sentinel survived\n"
        assert stderr == b""
    finally:
        if subject.returncode is None:
            if isolated:
                assert os.getpgid(subject.pid) == subject.pid
                assert os.getsid(subject.pid) == subject.pid
                os.killpg(subject.pid, signal.SIGKILL)
            else:
                subject.kill()
        await asyncio.wait_for(subject.communicate(), timeout=5)
