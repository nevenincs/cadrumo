"""Canonical Google configuration capabilities bound to one worker profile."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .google_configuration_operation_contracts import GoogleConfigurationProjection, GoogleConfigurationRequest


class GoogleConfigurationCommit(Protocol):
    """Admit only an actual canonical local credential/configuration write."""

    def __call__[ResultT](self, save: Callable[[], ResultT], *, changed: Callable[[ResultT], bool]) -> ResultT:
        """Return canonical acknowledgement after the protected physical save."""
        ...


class GoogleConfigurationHandoff(Protocol):
    """Renew authority before one named outbound boundary, outside its network call."""

    def __call__(self, action: str, *, writes: bool = False) -> None:
        """Record admitted uncertainty only after the authority check succeeds."""
        ...


class GoogleConfigurationAcknowledgement(Protocol):
    """Report one canonical positive acknowledgement without secret/provider data."""

    def __call__(self, action: str, *, writes: bool = False) -> None:
        """Settle the admitted boundary and account for actual remote writes."""
        ...


class GoogleConfigurationRun(Protocol):
    """Run the existing owning service without importing adapters into application."""

    def __call__(
        self,
        request: GoogleConfigurationRequest,
        *,
        secret: memoryview | None,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
        terminal_admission: Callable[[], None] | None,
    ) -> GoogleConfigurationProjection:
        """Return only complete non-secret current human output facts."""
        ...


@dataclass(frozen=True, slots=True)
class GoogleConfigurationOperationPorts:
    """Immutable profile/pin binding and the canonical configuration dispatcher."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    run: GoogleConfigurationRun
    prepare_consent: Callable[[], None]


class GoogleConfigurationOperationPortsFactory(Protocol):
    """Construct local capabilities without acquiring provider credentials."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> GoogleConfigurationOperationPorts:
        """Bind the exact authenticated worker profile and retained publication."""
        ...


__all__ = [
    "GoogleConfigurationAcknowledgement",
    "GoogleConfigurationCommit",
    "GoogleConfigurationHandoff",
    "GoogleConfigurationOperationPorts",
    "GoogleConfigurationOperationPortsFactory",
    "GoogleConfigurationRun",
]
