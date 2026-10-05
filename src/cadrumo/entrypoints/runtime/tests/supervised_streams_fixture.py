"""Supervised stream hygiene in a disposable process that starts its own descendant.

Modes:
- ``streams``: take the launch streams, start an inheriting grandchild, write
  stray text through every Python and native route, send one protocol line,
  release the private announcement descriptor, then wait for the test while
  the grandchild is still alive.
- ``failure``: run the runtime entrypoint supervised with an owner that fails
  unexpectedly.
- ``elevated``: run the runtime entrypoint supervised from a token that reads
  as fully elevated, with an owner that records whether it was reached.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import threading
import time
import warnings
from collections.abc import Mapping
from pathlib import Path

from cadrumo.adapters.local_runtime.tests.process_support import fixture_environment, native_python
from cadrumo.adapters.local_runtime.windows_token_elevation import WindowsTokenElevationType
from cadrumo.application.runtime.contracts import RuntimeExitReason
from cadrumo.core.logging import get_logger
from cadrumo.entrypoints.runtime import main as runtime_main
from cadrumo.entrypoints.runtime.shutdown import RuntimeStop
from cadrumo.entrypoints.runtime.supervised_channel import (
    SupervisedRuntime,
    SupervisorChannel,
    route_diagnostics_to_redacted_logging,
    take_supervisor_streams,
)
from cadrumo.entrypoints.runtime.supervised_protocol import RuntimeBusy

_GRANDCHILD = (
    "import os, sys, time\n"
    "sys.stdout.write('grandchild stdout\\n'); sys.stdout.flush()\n"
    "sys.stderr.write('grandchild stderr\\n'); sys.stderr.flush()\n"
    "os.write(1, b'grandchild native\\n')\n"
    "time.sleep(30)\n"
)


def _inheritable(descriptor: int) -> list[bool]:
    flags = [os.get_inheritable(descriptor)]
    if sys.platform == "win32":
        import msvcrt

        flags.append(os.get_handle_inheritable(msvcrt.get_osfhandle(descriptor)))
    return flags


def _fail_in_thread() -> None:
    raise ZeroDivisionError("synthetic thread failure")


def _publish(root: Path, result: dict[str, object]) -> None:
    pending = root / "result.pending"
    pending.write_text(json.dumps(result), encoding="ascii")
    pending.replace(root / "result.json")


async def _streams(root: Path) -> None:
    logger = get_logger("cadrumo.entrypoints.runtime.tests.supervised_streams_fixture")
    streams = take_supervisor_streams()
    if streams.commands is None or streams.announcements is None:
        raise RuntimeError("the test launcher supplies both protocol streams")
    route_diagnostics_to_redacted_logging(logger)
    channel = SupervisorChannel(streams, logger=logger)
    channel.start(lambda _command: None)
    inheritable = _inheritable(streams.commands) + _inheritable(streams.announcements)
    # Without redirection the grandchild receives the standard handles, and
    # close_fds=False passes every other inheritable descriptor and handle.
    grandchild = await asyncio.create_subprocess_exec(
        str(native_python()), "-c", _GRANDCHILD, env=fixture_environment(), close_fds=False
    )
    try:
        print("stray print")
        sys.stdout.write("stray stdout\n")
        sys.stderr.write("stray stderr\n")
        os.write(1, b"stray native stdout\n")
        os.write(2, b"stray native stderr\n")
        warnings.warn("synthetic stray warning", UserWarning, stacklevel=1)
        failing = threading.Thread(target=_fail_in_thread, name="synthetic-failing-thread")
        failing.start()
        failing.join()
        channel.announce(RuntimeBusy())
        channel.close(timeout=5)
        os.close(streams.announcements)
        _publish(root, {"grandchild": grandchild.pid, "inheritable": inheritable})
        # The test now reads end of file only if no descendant holds the pipe.
        deadline = time.monotonic() + 20
        while not (root / "release").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("the test did not release the fixture")
            await asyncio.sleep(0.02)
    finally:
        if grandchild.returncode is None:
            grandchild.kill()
        await grandchild.wait()


def _failure(arguments: list[str]) -> None:
    def failing_owner(
        _options: argparse.Namespace,
        _stop: RuntimeStop,
        _previous: Mapping[signal.Signals, object],
        _supervision: SupervisedRuntime | None,
    ) -> RuntimeExitReason:
        raise LookupError("synthetic unexpected failure")

    # No real launch reaches a non-refusal failure, so the owner is replaced
    # in this disposable process; the mapping under test stays real.
    vars(runtime_main)["_run_runtime_owner"] = failing_owner
    raise SystemExit(runtime_main.run(arguments))


def _elevated(root: Path, arguments: list[str]) -> None:
    def recording_owner(
        _options: argparse.Namespace,
        _stop: RuntimeStop,
        _previous: Mapping[signal.Signals, object],
        _supervision: SupervisedRuntime | None,
    ) -> RuntimeExitReason:
        (root / "owner-reached").write_text("reached", encoding="ascii")
        return RuntimeExitReason.SUPERVISOR_STOP

    # No test host can be given a full elevated token on demand, so the native
    # read is replaced in this disposable process; the refusal routing is real.
    vars(runtime_main)["current_process_token_elevation_type"] = lambda: WindowsTokenElevationType.FULL
    vars(runtime_main)["_run_runtime_owner"] = recording_owner
    raise SystemExit(runtime_main.run(arguments))


def main() -> None:
    mode, root = sys.argv[1], Path(sys.argv[2])
    if mode == "streams":
        asyncio.run(_streams(root))
    elif mode == "failure":
        _failure(sys.argv[3:])
    elif mode == "elevated":
        _elevated(root, sys.argv[3:])
    else:
        raise ValueError("unknown supervised stream fixture mode")


if __name__ == "__main__":
    main()
