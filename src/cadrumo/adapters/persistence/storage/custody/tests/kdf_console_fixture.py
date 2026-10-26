"""Report which processes share this disposable process's console while a KDF worker is ready.

The test launches this module with a console of its own, so the probe never
reads or changes the test runner's console. Modes:
- ``shared``: launch the worker as an unsupervised runtime does.
- ``isolated``: isolate helper children first, as a supervised runtime does.

The second argument is the storage root for the worker's temporary directory.
One JSON line is written to standard output.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path

from ......core.child_console import isolate_child_consoles
from ......core.config import Settings
from .._kdf_worker_supervision import _SupervisedKdfWorker

_MAX_CONSOLE_PROCESSES = 64


def _console_process_ids() -> list[int]:
    if sys.platform != "win32":
        raise RuntimeError("the console probe is Windows only")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = (ctypes.c_uint32 * _MAX_CONSOLE_PROCESSES)()
    count = int(kernel32.GetConsoleProcessList(buffer, _MAX_CONSOLE_PROCESSES))
    if not 0 < count <= _MAX_CONSOLE_PROCESSES:
        raise ctypes.WinError(ctypes.get_last_error())
    return sorted(int(pid) for pid in buffer[:count])


def main() -> None:
    mode, root = sys.argv[1], Path(sys.argv[2])
    if mode == "isolated":
        isolate_child_consoles()
    elif mode != "shared":
        raise ValueError("unknown KDF console fixture mode")
    settings = Settings(cadrumo_local_storage_root=root)
    # The ready handshake also proves the worker sits in its job object.
    with _SupervisedKdfWorker(deadline=time.monotonic() + 120, settings=settings) as worker:
        process = worker._process
        if process is None:
            raise RuntimeError("a ready worker has a process")
        result = {"fixture": os.getpid(), "worker": process.pid, "console": _console_process_ids()}
    sys.stdout.write(json.dumps(result) + "\n")


if __name__ == "__main__":
    main()
