"""Send a console Ctrl+C to a runtime that inherited the "ignore Ctrl+C" flag.

The test launches this module with a hidden console of its own, so the event
never reaches the test runner. Modes:
- ``supervised`` and ``unsupervised``: set the ignore flag, which every child
  inherits, start the runtime on this console, wait until it serves, send
  Ctrl+C to the whole console, and report how the runtime ended.
- ``without-reenable``: the same as ``unsupervised`` with a runtime whose
  startup does not restore Ctrl+C processing. It reports whether the runtime
  was still serving a while after the event.
- ``runtime-without-reenable``: the runtime that mode starts. The restoring
  call is replaced in this disposable process; the rest of the runtime is real.

Arguments after the mode: the storage root, then the runtime's own arguments
for ``runtime-without-reenable``. One JSON line is written to standard output.
"""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from importlib.metadata import version
from pathlib import Path
from typing import IO

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.tests.process_support import fixture_arguments, fixture_environment, native_python
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalError

_STARTUP_SECONDS = 90
_UNSEEN_SECONDS = 5
_CTRL_C_EVENT = 0
_RUNTIME_MODULE = "cadrumo.entrypoints.runtime"
_THIS_MODULE = "cadrumo.entrypoints.runtime.tests.console_interrupt_fixture"


def _kernel32() -> ctypes.CDLL:
    if sys.platform != "win32":
        raise RuntimeError("the console interrupt fixture is Windows only")
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _require(succeeded: object) -> None:
    if sys.platform != "win32":
        raise RuntimeError("the console interrupt fixture is Windows only")
    if not succeeded:
        raise ctypes.WinError(ctypes.get_last_error())


def _runtime_command(mode: str, endpoint: WindowsRuntimeEndpoint, root: Path) -> tuple[str, ...]:
    arguments = (
        "--storage-root",
        str(root),
        "--storage-identity",
        endpoint.storage_identity,
        "--expected-version",
        version("cadrumo"),
    )
    if mode == "supervised":
        arguments = (*arguments, "--supervised")
    module = (_THIS_MODULE, "runtime-without-reenable", str(root)) if mode == "without-reenable" else (_RUNTIME_MODULE,)
    return (str(native_python()), "-I", *fixture_arguments(*module, *arguments))


def _await_serving(endpoint: WindowsRuntimeEndpoint, runtime: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + _STARTUP_SECONDS
    while time.monotonic() < deadline and runtime.poll() is None:
        try:
            connection = VerifiedRuntimeConnection(
                endpoint.connect(timeout=2),
                expected=RuntimeClientHello(
                    product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                ),
                deadline=time.monotonic() + 5,
            )
        except (OSError, RuntimeRefusalError):
            time.sleep(0.2)
            continue
        connection.close()
        return
    raise TimeoutError("the runtime did not start serving")


def _await_ready(announcements: IO[bytes]) -> list[object]:
    # The launch pipe is read only after the ready line names a serving runtime.
    line = announcements.readline()
    loaded: object = json.loads(line)
    if not isinstance(loaded, dict) or loaded.get("type") != "ready":
        raise RuntimeError("the supervised runtime did not report ready first")
    return [loaded]


def _interrupt(mode: str, root: Path) -> dict[str, object]:
    kernel32 = _kernel32()
    # This process and every child it starts from now on ignore Ctrl+C.
    _require(kernel32.SetConsoleCtrlHandler(None, True))
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    environment = fixture_environment()
    environment["CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE"] = "1"
    environment["CADRUMO_LOG_DIR"] = str(root / "logs")
    supervised = mode == "supervised"
    result: dict[str, object] = {}
    with (root / "runtime.stderr").open("wb") as errors:
        runtime = subprocess.Popen(  # noqa: S603 -- exact interpreter and fixed in-repository modules.
            _runtime_command(mode, endpoint, root),
            cwd=root,
            env=environment,
            stdin=subprocess.PIPE if supervised else subprocess.DEVNULL,
            stdout=subprocess.PIPE if supervised else subprocess.DEVNULL,
            stderr=errors,
        )
        try:
            if supervised and runtime.stdout is not None:
                announcements = _await_ready(runtime.stdout)
            else:
                _await_serving(endpoint, runtime)
                announcements = []
            _require(kernel32.GenerateConsoleCtrlEvent(_CTRL_C_EVENT, 0))
            if mode == "without-reenable":
                time.sleep(_UNSEEN_SECONDS)
                result["serving_after_interrupt"] = runtime.poll() is None
            else:
                result["exit_code"] = runtime.wait(timeout=_STARTUP_SECONDS)
                if runtime.stdout is not None:
                    announcements.extend(json.loads(line) for line in runtime.stdout.read().splitlines())
                result["announcements"] = announcements
        finally:
            if runtime.poll() is None:
                runtime.kill()
            runtime.wait(timeout=10)
            endpoint.close()
    return result


def _runtime_without_reenable(arguments: list[str]) -> None:
    from cadrumo.entrypoints.runtime import main as runtime_main

    vars(runtime_main)["_accept_console_interrupts"] = lambda: None
    raise SystemExit(runtime_main.run(arguments))


def main() -> None:
    mode, root = sys.argv[1], Path(sys.argv[2])
    if mode == "runtime-without-reenable":
        _runtime_without_reenable(sys.argv[3:])
    elif mode in {"supervised", "unsupervised", "without-reenable"}:
        result = _interrupt(mode, root)
        sys.stdout.write(json.dumps(result) + "\n")
    else:
        raise ValueError("unknown console interrupt fixture mode")


if __name__ == "__main__":
    main()
