"""Queue a verified runtime's systemd stop before releasing its ownership."""

from __future__ import annotations

import asyncio
import os

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.management import RuntimeManagerProcessState, RuntimeServiceBinding
from .linux_manager import LinuxUserManager
from .manager_commands import NativeManagerCommand, run_manager_command
from .service_definitions import runtime_service_name


class LinuxManagedRuntimeStop:
    """Native stop preparation, called only after separate OS-owner consent.

    The manager's stop job suppresses restart before SIGTERM begins the existing
    runtime drain. Its completion is not a domain settlement receipt. No task
    enablement, login-autostart policy or unattended authorization is changed.
    """

    def __init__(self, binding: RuntimeServiceBinding) -> None:
        """Bind exact installed provisioning and this live runtime process."""
        self._manager = LinuxUserManager(binding)
        self._name = runtime_service_name(binding) + ".service"
        self._pid = os.getpid()

    async def _queue(self) -> None:
        try:
            async with asyncio.timeout(5):
                current = await self._manager.inspect()
                if not current.available or not current.provisioned:
                    raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                if not current.binding_matches:
                    raise RuntimeRefusalError(RuntimeRefusalCode.VERSION_MISMATCH)
                if current.process_state is not RuntimeManagerProcessState.RUNNING or os.getpid() != self._pid:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                owner = await run_manager_command(
                    NativeManagerCommand.SYSTEMCTL,
                    ("--user", "--no-pager", "--no-ask-password", "show", self._name, "--property=MainPID", "--value"),
                )
                if owner.returncode != 0 or owner.output != f"{self._pid}\n":
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                # Revalidates exact provisioning before queuing. A timeout or
                # lost acknowledgement may still mean the manager accepted it.
                await self._manager.stop()
        except TimeoutError:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED) from None

    def __call__(self) -> None:
        """Prepare stop on the server's bounded connection thread."""
        asyncio.run(self._queue())
