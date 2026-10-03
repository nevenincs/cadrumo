"""Profile worker endpoints over the runtime's native verified byte transport."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .posix import posix_owner_uid
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
        # The endpoint itself creates and verifies an owner-only namespace
        # under the sticky root-owned temporary directory.
        return PosixRuntimeEndpoint(
            storage_root=storage_root,
            namespace=Path("/tmp") / f"cdr-{posix_owner_uid()}-worker-{worker_namespace.hex}",  # noqa: S108
        )
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
