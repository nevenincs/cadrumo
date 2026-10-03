#!/usr/bin/python3
"""Finite, nonsecret process tree for an isolated user-systemd stop test."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import time
from pathlib import Path

_CHILD = """
import os, signal, sys, time
from pathlib import Path
root = Path(sys.argv[1])
def term(_number, _frame):
    (root / 'child-term').write_text(str(os.getpid()), encoding='ascii')
    raise SystemExit(0)
signal.signal(signal.SIGTERM, term)
# Bound an orphan even if the requesting test process disappears.
signal.alarm(45)
(root / 'child-ready').write_text(str(os.getpid()), encoding='ascii')
while True:
    time.sleep(0.1)
"""


def _service(arguments: list[str]) -> None:
    if sys.platform != "linux":
        raise RuntimeError("systemd stop fixture requires Linux")
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--storage-root", required=True)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--managed-session", action="store_true")
    options = parser.parse_args(arguments)
    root = Path(options.storage_root)
    if (
        root.resolve() != Path(__file__).resolve().parent
        or options.expected_version != "synthetic-cohort"
        or not options.managed_session
        or not options.storage_identity
    ):
        raise SystemExit(2)

    def lifetime_expired(_number: int, _frame: object) -> None:
        # Exit successfully so Restart=on-failure cannot revive an orphaned test unit.
        raise SystemExit(0)

    signal.signal(signal.SIGALRM, lifetime_expired)
    signal.alarm(45)
    mode = (root / "mode").read_text(encoding="ascii")
    child_pid = os.posix_spawn(
        sys.executable,
        (sys.executable, "-c", _CHILD, str(root)),
        {"PATH": "/usr/bin:/bin"},
    )
    try:
        deadline = time.monotonic() + 5
        while not (root / "child-ready").is_file():
            if time.monotonic() >= deadline:
                raise RuntimeError("synthetic child did not start")
            time.sleep(0.02)

        def terminate(_number: int, _frame: object) -> None:
            (root / "term").write_text(str(os.getpid()), encoding="ascii")
            deadline = time.monotonic() + 10
            while not (root / "release").exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            (root / "main-only-term").write_text(str(not (root / "child-term").exists()), encoding="ascii")
            if mode == "crash":
                os._exit(2)
            os.kill(child_pid, signal.SIGTERM)
            os.waitpid(child_pid, 0)
            (root / "settled").write_text("yes", encoding="ascii")
            os._exit(0)

        signal.signal(signal.SIGTERM, terminate)
        count_path = root / "boot-count"
        count = int(count_path.read_text(encoding="ascii")) + 1 if count_path.exists() else 1
        count_path.write_text(str(count), encoding="ascii")
        (root / "boot").write_text(f"{os.getpid()} {child_pid}", encoding="ascii")
        while True:
            time.sleep(0.1)
    finally:
        if os.waitpid(child_pid, os.WNOHANG) == (0, 0):
            os.kill(child_pid, signal.SIGTERM)
            os.waitpid(child_pid, 0)


async def _queue_stop(root: Path) -> None:
    if sys.platform != "linux":
        raise RuntimeError("systemd stop fixture requires Linux")
    from cadrumo.adapters.local_runtime.linux_manager import LinuxUserManager
    from cadrumo.adapters.local_runtime.posix import posix_storage_identity
    from cadrumo.application.runtime.management import RuntimeServiceBinding

    manager = LinuxUserManager(
        RuntimeServiceBinding(
            executable=str(root / "synthetic-runtime"),
            storage_root=str(root),
            storage_identity=posix_storage_identity(root),
            os_owner_id=str(os.getuid()),
            product_version="synthetic-cohort",
        )
    )
    await manager.stop()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "queue-stop":
        asyncio.run(_queue_stop(Path(sys.argv[2])))
    else:
        _service(sys.argv[1:])
