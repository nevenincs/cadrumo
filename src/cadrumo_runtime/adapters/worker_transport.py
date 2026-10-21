"""Profile worker endpoints over the runtime's native verified byte transport."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.posix_endpoint import PosixEndpoint
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_client.transport.windows_channel import WindowsChannel

WorkerChannel = WindowsChannel | PosixChannel
WorkerEndpoint = WindowsEndpoint | PosixEndpoint


def worker_endpoint(*, storage_root: Path, worker_namespace: UUID) -> WorkerEndpoint:
    """Give each worker channel an immutable owner-only native namespace."""
    if sys.platform == "win32":
        return WindowsEndpoint(storage_root=storage_root, worker_namespace=worker_namespace)
    if sys.platform in {"linux", "darwin"}:
        # The endpoint creates and verifies the configured owner-only socket directory.
        return PosixEndpoint(
            storage_root=storage_root,
            worker_namespace=worker_namespace,
        )
    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
