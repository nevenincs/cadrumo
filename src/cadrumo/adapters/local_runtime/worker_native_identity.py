"""Private worker namespace identity and retained native peer process verification."""

from __future__ import annotations

from uuid import UUID, uuid5

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .linux_worker_process import LinuxProcessScope
from .posix_channel import PosixRuntimeChannel
from .windows_process import WindowsProcessScope
from .worker_transport import WorkerChannel


def worker_operation_namespace(worker_id: UUID) -> UUID:
    """Separate private execution I/O from authority-held custody control calls."""
    return uuid5(worker_id, "cadrumo-profile-operations")


def verify_worker_native_pid(
    channel: WorkerChannel, scope: WindowsProcessScope | LinuxProcessScope, os_owner_id: str
) -> int:
    """Require the exact native worker process and owner on its retained channel."""
    if isinstance(scope, LinuxProcessScope):
        if not isinstance(channel, PosixRuntimeChannel):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return scope.verify_worker(channel, owner_id=os_owner_id)
    peer = channel.peer
    process_id = peer.process_id
    if process_id is None or process_id not in scope.active_process_ids() or peer.os_owner_id != os_owner_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    return process_id
