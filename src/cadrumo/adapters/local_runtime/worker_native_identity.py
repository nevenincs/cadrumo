"""Private worker namespace identity and retained native peer process verification."""

from __future__ import annotations

from uuid import UUID, uuid5

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .linux_worker_process import LinuxProcessScope
from .macos_worker_process import MacosProcessScope
from .posix_channel import PosixRuntimeChannel
from .windows_channel import WindowsRuntimeChannel
from .windows_process import WindowsProcessScope
from .worker_transport import WorkerChannel


def worker_operation_namespace(worker_id: UUID) -> UUID:
    """Separate private execution I/O from authority-held custody control calls."""
    return uuid5(worker_id, "cadrumo-profile-operations")


def verify_worker_native_pid(
    channel: WorkerChannel, scope: WindowsProcessScope | LinuxProcessScope | MacosProcessScope, os_owner_id: str
) -> int:
    """Require the exact native worker process and owner on its retained channel."""
    if isinstance(scope, LinuxProcessScope | MacosProcessScope):
        if not isinstance(channel, PosixRuntimeChannel):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        return scope.verify_worker(channel, owner_id=os_owner_id)
    peer = channel.peer
    process_id = peer.process_id
    if not isinstance(channel, WindowsRuntimeChannel) or process_id is None or peer.os_owner_id != os_owner_id:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    import pywintypes
    import win32api
    import win32con

    try:
        process = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE, False, process_id)
    except pywintypes.error:
        raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED) from None
    try:
        # The channel compares this handle with its retained authenticated birth.
        # Job membership then admits packaged worker descendants as well as roots.
        channel.verify_peer_process(int(process))
        if not scope.contains_process(int(process)):
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
    finally:
        win32api.CloseHandle(process)
    return process_id
