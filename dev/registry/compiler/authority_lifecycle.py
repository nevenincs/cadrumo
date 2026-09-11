"""Development-only lifecycle notifications for mutable authority cache maintenance."""

from __future__ import annotations

from typing import Protocol


class RegistryAuthorityLifecycleObserver(Protocol):
    """Observe a development compiler-cache reset transition."""

    def registry_cache_reset_requested(self) -> None:
        """Observe that a reset has been requested."""
        ...

    def registry_cache_reset_acquired(self) -> None:
        """Observe that exclusive reset ownership has been acquired."""
        ...


class SilentRegistryAuthorityLifecycleObserver:
    """Default observer for development cache maintenance."""

    def registry_cache_reset_requested(self) -> None:
        """Ignore the reset request."""

    def registry_cache_reset_acquired(self) -> None:
        """Ignore acquisition of reset ownership."""


SILENT_REGISTRY_AUTHORITY_LIFECYCLE_OBSERVER = SilentRegistryAuthorityLifecycleObserver()
