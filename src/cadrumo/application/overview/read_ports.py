"""One exact-profile capture seam for canonical overview read builders."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ...domain.calculations.registry.authority import PinnedAuthorityOperation

if TYPE_CHECKING:
    from .read_payload import OverviewReadPayload
    from .read_request import OverviewReadRequest


class OverviewReadPorts(Protocol):
    """Return closed captures from existing builders under one held pin."""

    @property
    def bucket_id(self) -> str:
        """Return the immutable selected bucket identity."""
        ...

    def capture(self, request: OverviewReadRequest, *, operation: PinnedAuthorityOperation) -> OverviewReadPayload:
        """Capture only the requested overview projection inside its worker."""
        ...


class OverviewReadPortsFactory(Protocol):
    """Compose the selected profile's readers under the retained authority."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> OverviewReadPorts:
        """Return a bound read bundle with no mutation capability."""
        ...


__all__ = ["OverviewReadPorts", "OverviewReadPortsFactory"]
