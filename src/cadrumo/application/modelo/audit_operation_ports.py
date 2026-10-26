"""Immutable exact-profile evidence capabilities for the registered audit family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..evidence.ports import EvidenceBundlePorts


@dataclass(frozen=True, slots=True)
class ModeloAuditOperationPorts:
    """One selected worker and publication pin with canonical evidence repositories."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    evidence: EvidenceBundlePorts


class ModeloAuditOperationPortsFactory(Protocol):
    """Compose only repositories addressed to the admitted worker's profile."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> ModeloAuditOperationPorts:
        """Bind canonical evidence ports to one immutable profile and supplied pin."""
        ...
