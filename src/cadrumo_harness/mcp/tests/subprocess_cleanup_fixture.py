"""Bounded POSIX processes for exercising cleanup outside the test runner's group."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _record(root: Path, name: str) -> None:
    if sys.platform == "win32":
        raise RuntimeError("POSIX fixture requires sessions and process groups")
    (root / f"{name}.json").write_text(
        json.dumps({"pid": os.getpid(), "pgid": os.getpgrp(), "sid": os.getsid(0)}), encoding="utf-8"
    )


def _running(pid: int) -> bool:
    # A killed orphan may remain a zombie until the OS reaps it. Do not claim
    # reaping from this observer, which is not that process's parent.
    async def inspect() -> bytes:
        process = await asyncio.create_subprocess_exec(
            "/bin/ps",
            "-o",
            "stat=",
            "-p",
            str(pid),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=2)
            assert process.returncode in (0, 1), (process.returncode, stderr)
            assert not stderr, stderr
            assert bool(stdout.strip()) == (process.returncode == 0)
            return stdout
        finally:
            if process.returncode is None:
                process.kill()
                await asyncio.wait_for(process.wait(), timeout=2)

    state = asyncio.run(inspect()).decode().strip()
    return bool(state) and not state.startswith("Z")


def _wait_stopped(pid: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while _running(pid):
        if time.monotonic() >= deadline:
            raise AssertionError(f"fixture process {pid} did not stop")
        time.sleep(0.05)


def _child(root: Path, mode: str) -> None:
    if sys.platform == "win32":
        raise RuntimeError("POSIX fixture requires fork and alarm")
    _record(root, "child")
    if mode != "direct":
        if os.fork() == 0:
            signal.alarm(15)
            _record(root, "leaf")
            time.sleep(12)
            os._exit(0)
        deadline = time.monotonic() + 5
        while not (root / "leaf.json").exists():
            if time.monotonic() >= deadline:
                raise AssertionError("leaf did not start")
            time.sleep(0.01)
    if mode != "exited":
        time.sleep(20)


def _subject(root: Path, mode: str, api: str) -> None:
    from cadrumo_harness.mcp.call_runtime import run_captured, run_supervised

    if sys.platform == "win32":
        raise RuntimeError("POSIX fixture requires sessions and process groups")
    assert os.getpid() == os.getpgrp() == os.getsid(0)
    sys.stdout.write("ready\n")
    sys.stdout.flush()
    assert sys.stdin.readline() == "go\n"
    sentinel = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(25)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert os.getpgid(sentinel.pid) == os.getpgrp()
        argv = [sys.executable, __file__, "child", str(root), mode]
        if api == "captured":
            try:
                run_captured(argv, timeout_s=1)
            except subprocess.TimeoutExpired as error:
                assert error.cmd == argv
                assert error.timeout == 1
            else:
                raise AssertionError("captured call did not time out")
        else:
            result = run_supervised(argv, timeout_s=1, encoding="utf-8")
            assert result.timed_out
            assert result.returncode == -1
        assert sentinel.poll() is None, "cleanup killed the caller's same-group sentinel"
        child = json.loads((root / "child.json").read_text(encoding="utf-8"))
        assert child["pid"] == child["pgid"] == child["sid"]
        assert child["pgid"] != os.getpgrp()
        _wait_stopped(child["pid"], 3)
        if mode != "direct":
            leaf = json.loads((root / "leaf.json").read_text(encoding="utf-8"))
            assert leaf["pgid"] == child["pgid"]
            assert leaf["sid"] == child["sid"]
            if mode == "exited":
                # Cleanup deliberately declines group signalling after the
                # leader exits. The leaf's own finite lifetime supplies cleanup.
                assert _running(leaf["pid"])
                _wait_stopped(leaf["pid"], 15)
            else:
                _wait_stopped(leaf["pid"], 3)
        sys.stdout.write("timeout verified; sentinel survived\n")
        sys.stdout.flush()
    finally:
        if sentinel.poll() is None:
            sentinel.terminate()
        sentinel.wait(timeout=3)


def main() -> None:
    """Run only finite synthetic workloads, with an independent hard deadline."""
    if sys.platform == "win32":
        raise RuntimeError("POSIX fixture requires alarm")
    signal.alarm(35)
    role, root = sys.argv[1], Path(sys.argv[2])
    if role == "child":
        _child(root, sys.argv[3])
    elif role == "subject":
        _subject(root, sys.argv[3], sys.argv[4])
    else:
        raise AssertionError(f"unknown fixture role: {role}")


if __name__ == "__main__":
    main()
