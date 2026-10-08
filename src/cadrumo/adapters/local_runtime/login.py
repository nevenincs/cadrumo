"""Select demonstrated native login provenance for an already verified local peer."""

import sys

from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.login import RuntimeLoginEvidence
from .posix_channel import PosixRuntimeChannel
from .windows_channel import WindowsRuntimeChannel


def capture_runtime_login(channel: RuntimeByteChannel) -> RuntimeLoginEvidence:
    """Use the retained transport handle; unsupported provenance refuses before secrets."""
    if isinstance(channel, WindowsRuntimeChannel):
        return channel.capture_login()
    if sys.platform in {"linux", "darwin"} and isinstance(channel, PosixRuntimeChannel):
        return channel.capture_login()
    raise RuntimeRefusalError(RuntimeRefusalCode.CONTAINMENT_UNAVAILABLE)
