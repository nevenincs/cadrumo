"""Select demonstrated native login provenance for an already verified local peer."""

import sys

from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.windows_channel import WindowsChannel


def capture_runtime_login(channel: ByteChannel) -> LoginEvidence:
    """Use the retained transport handle; unsupported provenance refuses before secrets."""
    if isinstance(channel, WindowsChannel):
        from .windows_login import capture_windows_login

        with channel.pinned_peer_process_handle() as handle:
            return capture_windows_login(handle, expected_owner=channel.peer.os_owner_id)
    if isinstance(channel, PosixChannel) and sys.platform == "linux":
        from .linux_login import capture_linux_login

        with channel.capture_peer_pidfd() as descriptor:
            return capture_linux_login(descriptor, expected_owner=channel.peer.os_owner_id)
    if isinstance(channel, PosixChannel) and sys.platform == "darwin":
        from .macos_login import capture_macos_login

        with channel.pinned_peer_socket() as sock:
            return capture_macos_login(sock, expected_owner=channel.peer.os_owner_id)
    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
