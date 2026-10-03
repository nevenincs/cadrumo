"""Profile worker endpoints over the runtime's native verified byte transport."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .posix_channel import PosixRuntimeChannel
from .posix_endpoint import PosixRuntimeEndpoint
from .windows import WindowsRuntimeEndpoint
from .windows_channel import WindowsRuntimeChannel

WorkerChannel = WindowsRuntimeChannel | PosixRuntimeChannel
WorkerEndpoint = WindowsRuntimeEndpoint | PosixRuntimeEndpoint


def worker_endpoint(*, storage_root: Path, worker_namespace: UUID) -> WorkerEndpoint:
    """Give each worker channel an immutable owner-only native namespace."""
    if sys.platform == "win32":
        return WindowsRuntimeEndpoint(storage_root=storage_root, worker_namespace=worker_namespace)
    if sys.platform == "linux":
        # The endpoint creates and verifies the configured owner-only socket directory.
        return PosixRuntimeEndpoint(
            storage_root=storage_root,
            worker_namespace=worker_namespace,
        )
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
