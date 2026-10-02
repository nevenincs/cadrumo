"""Immutable profile and authority binding for local Modelo 036 recording."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .m036_lifecycle_ports import M036LifecyclePorts


@dataclass(frozen=True, slots=True)
class M036OperationPorts:
    """The existing local declaration/event custody bound to one worker."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    lifecycle_ports: M036LifecyclePorts


class M036OperationPortsFactory(Protocol):
    """Compose encrypted storage within an already admitted exact-profile worker."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> M036OperationPorts:
        """Return the canonical local lifecycle capabilities without filing."""
        ...
