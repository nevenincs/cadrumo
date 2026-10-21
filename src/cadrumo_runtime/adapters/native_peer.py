"""Host-side revalidation of the native process that owns a channel."""

from __future__ import annotations

import sys

from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_client.transport.windows_channel import WindowsChannel


def require_live_native_peer(channel: ByteChannel) -> None:
    """Revalidate the exact peer incarnation before using host authority."""
    if isinstance(channel, WindowsChannel):
        channel.require_live_peer()
        return
    if not isinstance(channel, PosixChannel):
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    if sys.platform == "linux":
        with channel.capture_peer_pidfd():
            pass
        return
    if sys.platform == "darwin":
        from .macos_login import macos_peer_audit_token

        with channel.pinned_peer_socket() as sock:
            token = macos_peer_audit_token(sock, expected_owner=channel.peer.os_owner_id)
        if token.process_id != channel.peer.process_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return
    raise RefusalError(RefusalCode.CONTAINMENT_UNAVAILABLE)
