"""Runtime-owned selection of native or explicit development session admission."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from uuid import UUID

from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.login import RuntimeLoginEvidence, RuntimeLoginInventory
from ...application.user_profile.access_contracts import Availability, LoginEligibility, OsLoginContext
from ...core.config import load_settings
from .login import capture_runtime_login


@dataclass(frozen=True)
class RuntimeLoginPolicy:
    """One admission policy selected once at runtime startup, shared by every frontend."""

    capture: Callable[[RuntimeByteChannel], RuntimeLoginEvidence]
    inventory: Callable[[], RuntimeLoginInventory] | None


@dataclass(frozen=True)
class DevelopmentRuntimeLogin:
    """Same-account development admission lasting only for this runtime boot.

    This deliberately makes no native desktop or lock-state claim. Transport
    peer verification precedes capture; profile credentials and connection
    authorization remain owned by the normal application services.
    """

    os_owner_id: str
    runtime_boot_id: UUID
    stop: Event

    @property
    def login_id(self) -> str:
        """Keep reconnects stable within a boot, never across runtime replacement."""
        return f"development-runtime:{self.runtime_boot_id}"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        """Use the explicit development lifetime without probing an OS desktop."""
        active = not self.stop.is_set()
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=self.os_owner_id,
            active=active,
            locked=not active,
            unattended=LoginEligibility.ELIGIBLE if active else LoginEligibility.INELIGIBLE,
            credential_facilities=credential_facilities,
        )

    def capture(self, channel: RuntimeByteChannel) -> RuntimeLoginEvidence:
        """Reject foreign native owners even when session admission is relaxed."""
        if channel.peer.os_owner_id != self.os_owner_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if self.stop.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        return self

    def inventory(self) -> RuntimeLoginInventory:
        """Prevent native desktop inventory from undoing the explicit override."""
        return RuntimeLoginInventory(() if self.stop.is_set() else (self,), True)


def compose_runtime_login_policy(
    *,
    os_owner_id: str,
    runtime_boot_id: UUID,
    stop: Event,
    native_inventory: Callable[[], RuntimeLoginInventory] | None,
) -> RuntimeLoginPolicy:
    """Read core settings at the runtime, never an option supplied by a client."""
    if not load_settings().dev_runtime_session_override_enabled:
        return RuntimeLoginPolicy(capture_runtime_login, native_inventory)
    development = DevelopmentRuntimeLogin(os_owner_id, runtime_boot_id, stop)
    return RuntimeLoginPolicy(development.capture, development.inventory)
