"""Retain native Secret Service close diagnostics without replaying operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from .....core.async_cleanup import AsyncResourceCleanupError
from .linux_secret_contracts import SESSION_IFACE

if TYPE_CHECKING:
    pass


class SecretBusResource(Protocol):
    """Native close and session-close operations required during cleanup."""

    def close(self) -> None:
        """Disconnect the owned native transport."""
        ...

    def call(
        self,
        path: str,
        interface: str,
        method: str,
        signature: str = "",
        body: tuple[Any, ...] = (),
        *,
        destination: str | None = None,
    ) -> tuple[Any, ...]:
        """Send one bounded method request through the owned transport."""
        ...


def close_secret_bus_after_failure(
    bus: SecretBusResource, primary: BaseException, *, session_path: str | None = None
) -> None:
    """Retain close diagnostics; the bus disconnect owns final session settlement."""
    try:
        if session_path is None:
            bus.close()
        else:
            bus.call(session_path, SESSION_IFACE, "Close")
    except BaseException as cleanup:
        previous = primary.__dict__.get("cleanup_error")
        if isinstance(previous, AsyncResourceCleanupError):
            diagnostic = AsyncResourceCleanupError(
                (), (cleanup,), retry_task_name="linux-secret-store-cleanup", close_attempts=1
            )
            retained = previous.merged_with(diagnostic)
            retained.__cause__ = cleanup
            primary.__dict__["cleanup_error"] = retained
            if primary.__dict__.get("async_cleanup_error") is previous:
                primary.__dict__["async_cleanup_error"] = retained
        elif isinstance(previous, BaseException) and previous is not cleanup:
            primary.__dict__["cleanup_error"] = BaseExceptionGroup(
                "Linux secret store cleanup failed", (previous, cleanup)
            )
        elif cleanup is not primary:
            primary.__dict__["cleanup_error"] = cleanup
        primary.add_note("Secret-store close also failed; no native retry was retained")
