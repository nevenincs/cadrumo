"""Systemd MainPID watching one exact runtime parent and contained worker."""

from __future__ import annotations

import argparse
import os
import select
import subprocess
import sys
from pathlib import Path

from ...adapters.local_runtime.linux_pidfd import open_linux_pidfd
from ...adapters.local_runtime.linux_worker_process import (
    linux_process_start_identity,
    validated_linux_worker_arguments,
)
from ...application.runtime.contracts import RuntimeRefusalError


def run(arguments: list[str] | None = None) -> int:
    """Exit on parent or worker loss; systemd then kills the whole service cgroup."""
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--parent-start", required=True)
    parser.add_argument("--worker-script", type=Path)
    parser.add_argument("worker_arguments", nargs=argparse.REMAINDER)
    options = parser.parse_args(arguments)
    if sys.platform == "linux":
        if not sys.flags.isolated:
            return 2
        worker_arguments = options.worker_arguments
        if worker_arguments[:1] == ["--"]:
            worker_arguments = worker_arguments[1:]
        try:
            worker_arguments = validated_linux_worker_arguments(worker_arguments, worker_script=options.worker_script)
        except RuntimeRefusalError:
            return 2
        try:
            parent = Path("/proc") / str(options.parent_pid)
            if (
                parent.stat().st_uid != os.getuid()
                or linux_process_start_identity(options.parent_pid) != options.parent_start
            ):
                return 2
            descriptor = open_linux_pidfd(options.parent_pid)
        except (OSError, RuntimeRefusalError):
            return 2
        try:
            watcher = select.poll()
            watcher.register(descriptor, select.POLLIN | select.POLLERR | select.POLLHUP)
            # The PID may have been reused between reading /proc and opening the
            # pidfd. Recheck identity while holding the exact kernel process handle.
            try:
                same_parent = (
                    not watcher.poll(0)
                    and parent.stat().st_uid == os.getuid()
                    and linux_process_start_identity(options.parent_pid) == options.parent_start
                    and not watcher.poll(0)
                )
            except (OSError, RuntimeRefusalError):
                return 2
            if not same_parent:
                return 2
            environment = {
                "PATH": "/usr/bin:/bin",
                "LANG": "C",
                "LC_ALL": "C",
                "PYDANTIC_DISABLE_PLUGINS": "__all__",
            }
            try:
                worker = subprocess.Popen(  # noqa: S603 - fixed interpreter and verified worker arguments
                    (sys.executable, *worker_arguments),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=environment,
                    close_fds=True,
                    start_new_session=True,
                )
            except OSError:
                return 2
            while True:
                if watcher.poll(200):
                    return 2
                code = worker.poll()
                if code is not None:
                    return code
        finally:
            os.close(descriptor)
    return 2


if __name__ == "__main__":
    raise SystemExit(run())
