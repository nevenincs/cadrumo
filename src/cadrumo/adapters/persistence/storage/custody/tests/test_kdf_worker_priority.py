"""A supervised KDF child is scheduled ahead of normal-priority background work.

Argon2 lanes synchronise on every slice, so a derivation competing at equal
priority with a saturated host stretches from under a second to tens of
seconds. The case reads the real launched child's priority class back from the
operating system while it waits, attested, for its request.
"""

from __future__ import annotations

import ctypes
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest

from ......core.config import Settings
from .._kdf_process import WINDOWS_ABOVE_NORMAL_PRIORITY_CLASS
from .._kdf_worker_supervision import _SupervisedKdfWorker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_persistence_adapter,
    pytest.mark.skipif(sys.platform != "win32", reason="priority classes are a Windows scheduling property"),
]


def test_attested_kdf_child_runs_above_normal_priority(tmp_path: Path) -> None:
    worker = _SupervisedKdfWorker(
        deadline=time.monotonic() + 60, settings=Settings(cadrumo_local_storage_root=tmp_path)
    )
    with worker:
        process = worker._process
        assert process is not None and process.poll() is None
        if sys.platform == "win32":
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            priority = kernel32.GetPriorityClass(ctypes.c_void_p(int(cast(Any, process)._handle)))
            assert priority == WINDOWS_ABOVE_NORMAL_PRIORITY_CLASS, ctypes.get_last_error()
