"""Private worker namespace identity and retained native peer process verification."""

from __future__ import annotations

from uuid import UUID, uuid5

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.windows_channel import WindowsChannel

from .linux_worker_process import LinuxProcessScope
from .macos_worker_process import MacosProcessScope
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
        if not isinstance(channel, PosixChannel):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return scope.verify_worker(channel, owner_id=os_owner_id)
    peer = channel.peer
    process_id = peer.process_id
    if not isinstance(channel, WindowsChannel) or process_id is None or peer.os_owner_id != os_owner_id:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    import pywintypes
    import win32api
    import win32con

    try:
        process = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.SYNCHRONIZE, False, process_id)
    except pywintypes.error:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED) from None
    try:
        # The channel compares this handle with its retained authenticated birth.
        # Job membership then admits packaged worker descendants as well as roots.
        channel.verify_peer_process(int(process))
        if not scope.contains_process(int(process)):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    finally:
        win32api.CloseHandle(process)
    return process_id
