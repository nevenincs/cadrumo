"""Isolated native process whose shutdown watchdog may end its interpreter."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from threading import Event, Timer

from cadrumo.adapters.local_runtime.tests.process_support import fixture_environment, native_python
from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
from cadrumo.entrypoints.runtime.shutdown import RuntimeShutdownWatchdog


def main() -> None:
    root, mode = Path(sys.argv[1]), sys.argv[2]
    if mode not in {"blocked", "healthy"}:
        raise ValueError("unknown shutdown watchdog fixture mode")
    lifetime = Timer(20, os._exit, args=(124,))
    lifetime.daemon = True
    lifetime.start()
    scope = WindowsProcessScope()
    ready = root / "child-ready.json"
    trigger = root / "begin-shutdown"
    cleaned = root / "cleanup-complete"
    child = scope.launch(
        executable=native_python(),
        arguments=("-c", "import time; time.sleep(18)"),
        directory=root,
        environment=fixture_environment(),
    )
    stop = Event()
    try:
        with RuntimeShutdownWatchdog(stop, timeout=0.4):
            pending = ready.with_suffix(".pending")
            pending.write_text(json.dumps({"parent": os.getpid(), "child": child.pid}), encoding="ascii")
            pending.replace(ready)
            deadline = time.monotonic() + 10
            while not trigger.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("shutdown trigger did not arrive")
                time.sleep(0.01)
            stop.set()
            if mode == "blocked":
                # The watchdog must terminate this process before callbacks run.
                Event().wait(10)
            else:
                scope.terminate()
    finally:
        cleaned.write_text("completed", encoding="ascii")
        scope.terminate()
        lifetime.cancel()


if __name__ == "__main__":
    main()
